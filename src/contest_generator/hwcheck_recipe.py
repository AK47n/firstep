"""硬件检测的**配方机制**（工单 module-hwcheck/04）：库内数据 → 逐件检测小节。

## 这一层是什么

spec 把检测程序拆成两半：**框架**（LED 心跳、输出通道、逐件小节的位置、结尾
汇总）永远由 `hwcheck.py` 确定性渲染；**「每一件怎么测」**来自库内配方数据。
本模块就是那半数据的所有者——形状 / 解析 / 校验 / 渲染成 C 语句片段，一行
LLM 都不碰。

配方是**"怎么用这个模块"的元数据，不是模块逻辑**（票面边界）：它住在库根的
中央文件里，不写进模块源码、不改变"模块 = 纯驱动切片"的既有边界（ADR 0009
的关系记在工单 09 的新 ADR 里）。

## 落点（票面硬要求：跟随模块库根、不新增配置键）

模块库根 = `<库根>/modules`，配方文件 = `<库根>/hwcheck_recipes.json`——与
`topics/` / `references/` 同款"平级兄弟"布局（`config.py` 的库布局推导）。
用户把模块库换到别处时，配方自动跟着走，不必改任何配置键。

## 校验（本单的核心守卫）

**配方里引用的函数名必须能在该模块该平台的头文件接口清单里找到，找不到 =
构建期大声失败**（`HwCheckError` → 400 中文，点名 `slug / 平台 / 段 / 名字`）。

为什么不学骨架的 sanitize 把它改成注释：那是给 LLM 幻觉用的兜底（`skeleton.py`
的既定契约），而配方是**人写的库内数据**——错一个字母就该当场红，否则检测程序
会安静地少测一样东西，学生看到一片"OK"其实什么都没测（spec「不假装测过」）。

接口清单的判据与生成门禁**同一处**：`skeleton.format_interface_blocks` +
`extract_header_functions`——骨架自检说"这个调用存在"，配方校验就必须认同一套。

## 缺文件 vs 坏文件（两种事，两种处置）

* 文件**不在** = 能力缺失：老库 / 自定义库照常能生成检测工程，只是没有专精件
  （全走通用降级，归工单 07）——返回空配方库，不报错。
* 文件**坏了**（非法 JSON / 形状不对 / 引用了不存在的函数）= 数据错误：大声失败。
  读下去只会默默少测几件，比报错坏得多。

## 这一版只渲染"专精件"

没有配方的器件**不出小节**（通用降级是工单 07 的事）。所以本单的验收线
"专精件与未专精件外观可区分"靠的是专精小节的标题尾巴（`SECTION_TAG`）——
工单 07 的通用小节不带这个标记。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .clex import strip_comments
from .hwcheck_errors import HwCheckError
from .manifest import ModuleManifest
from .platforms import KNOWN_PLATFORMS
from .readme import sort_verification_order
__all__ = [
    "RECIPE_FILENAME",
    "SECTION_TAG",
    "RecipeCatalog",
    "RecipeConsole",
    "RecipeProbe",
    "RecipeRead",
    "RecipeSection",
    "HwCheckError",
    "c_string",
    "escape_c_string",
    "interface_names",
    "load_recipes",
    "parse_recipes",
    "recipe_library_path",
    "render_recipe_section",
    "render_recipe_summary",
    "resolve_sections",
    "unspecialized_message",
    "validate_recipes",
]

# 配方文件名（跟随模块库根的平级兄弟，见模块头「落点」）
RECIPE_FILENAME = "hwcheck_recipes.json"

# 专精小节的标题尾巴：**用户一眼看出"这件真测了"**（票面验收线）。未专精件
# 由工单 07 的通用降级渲染，标题不带这个标记——改标记只改这一处。
SECTION_TAG = "[专精]"

# 六段（spec 定义）。缺段 = 该件不支持该项，一律合法；全缺 = 空壳（不合法）。
_SEGMENTS = ("prereq", "init", "probe", "read", "console", "note")

# 段 → 中文名（报错文案里点名"哪一段"，用学生看得懂的说法）
_SEGMENT_NAMES = {
    "prereq": "前置调用",
    "init": "初始化",
    "probe": "通信探头",
    "read": "读数展示",
    "console": "控制台命令",
    "note": "平台说明",
}

# 数字字面量（含十六进制 / 后缀 / 负号）：期望值可以写成裸字面量
_NUMBER_RE = re.compile(r"^[+-]?(0[xX][0-9a-fA-F]+|\d+)([uUlL]{0,3})$")

# C 标识符（含宏名 / 常量名）
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")


@dataclass(frozen=True)
class RecipeConsole:
    """串口控制台命令（`console` 段）：一个字符 + 一句说明。

    单字符是**硬要求**（库内既有的 `r` / `y` / `g` / `o` / `b<N>` 都是单字符，
    命令循环按字符分派）；说明进检测页与回显（工单 06 消费）。跨器件的字符
    冲突判定归工单 06（命令表生成在那边）。
    """

    command: str
    description: str = ""


@dataclass(frozen=True)
class RecipeProbe:
    """通信探头（`probe` 段）：**自证**通信通没通，不信驱动的 init 返回值。

    规格判据三层里的第②层（板端 OK/FAIL）。`expect` 进渲染出的比较式
    （`r == 0x68`）——判定在板上算，不是渲染期猜出来的。
    """

    calls: tuple[str, ...] = ()
    expect: str = ""


@dataclass(frozen=True)
class RecipeRead:
    """一条读数展示（`read` 段）：整数 C 表达式 + 可选的单位。

    表达式必须是**整数**（常量或返回 int 的调用）——读数经 `hwcheck_report_int`
    回显，而"数据合理性只回显 + 给正常范围参考"（spec 判据第③层）不给阈值判决。
    """

    expression: str
    unit: str = ""


@dataclass(frozen=True)
class RecipeSection:
    """一件器件在一个平台上的检测小节（配方解析后的形态）。

    渲染只读这些字段（`render_recipe_section`）；`source` 只作报错时指路。
    """

    slug: str
    platform: str
    prereq: tuple[str, ...] = ()
    init: tuple[str, ...] = ()
    init_expect: str = ""
    probe: RecipeProbe | None = None
    read: tuple[RecipeRead, ...] = ()
    console: RecipeConsole | None = None
    note: tuple[str, ...] = ()
    source: str = ""

    @property
    def usable(self) -> bool:
        """有实际动作 = 不是空壳（地板断言用）。"""
        return bool(self.prereq or self.init or self.probe or self.read)


@dataclass(frozen=True)
class RecipeCatalog:
    """一件器件在一份配方文件里的全部平台条目（`slug → platform → 小节`）。"""

    slug: str
    sections: Mapping[str, RecipeSection]

    def for_platform(self, platform: str) -> RecipeSection | None:
        return self.sections.get(platform)

    @property
    def usable(self) -> bool:
        """至少一个平台的配方有实际动作（空壳不算"已专精"）。"""
        return any(section.usable for section in self.sections.values())


def recipe_library_path(module_library_dir: Path | str) -> Path:
    """配方文件路径（模块库根的平级兄弟，见模块头「落点」）。"""
    return Path(module_library_dir).parent / RECIPE_FILENAME


def _where(slug: str, platform: str, segment: str, source: str = "") -> str:
    """报错前缀：点名 `slug × 平台`（可选带文件位置）——找得到才改得动。"""
    head = f"{RECIPE_FILENAME} 的 {slug!r} × {platform}"
    if source:
        head += f"（{source}）"
    if not segment:
        return head
    return f"{head} 的{_SEGMENT_NAMES.get(segment, segment)}段"


def _segment_strings(
    segment: Any, key: str, where: str, *, field: str = "", required: bool = False
) -> tuple[str, ...]:
    """段内字符串数组字段（缺省 = 空元组；类型不对 = 中文大声失败点名到字段）。

    **段的形状统一是对象**（`{calls: [...]}` / `{lines: [...]}`）：显式键让
    "这一段的这一项叫什么"在文件里看得见（`calls` vs `lines` vs `command`），
    也避免"数组 = 哪种语义"的猜谜。缺失字段 = 该段不写这一项。

    `field` = 完整字段路径（`read.expressions` 这类），比裸键名好找；
    报错文案里同时给出段名与字段名，两种都能定位。
    """
    label = f"{where}的 {field or key!r}"
    if segment is None:
        raw: Any = None
    elif isinstance(segment, dict):
        raw = segment.get(key)
    else:
        raise HwCheckError(
            f"{where}必须是对象（{{…}}，字段 {field or key!r}），收到 {segment!r}"
        )
    if raw is None:
        if required:
            raise HwCheckError(f"{where}缺少必填字段 {field or key!r}")
        return ()
    if not isinstance(raw, list):
        raise HwCheckError(f"{label} 必须是字符串数组，收到 {raw!r}")
    out: list[str] = []
    for item in raw:
        text = item.strip() if isinstance(item, str) else ""
        if not text:
            raise HwCheckError(f"{label} 必须是非空字符串数组，收到 {item!r}")
        out.append(text)
    return tuple(out)


def _parse_read(where: str, raw: Any) -> tuple[RecipeRead, ...]:
    """读数展示段：`{expressions: [...]}` 或 `{items: [{expression, unit}…]}`。

    两种写法都收是为了让简单件写得短（`LED_CHANNEL_COUNT`）而带单位的件说得清
    （`{expression: "sr04_get_distance()", unit: "cm"}`）——**同一条判据**
    （表达式必须是整数 C 表达式）不变，函数名判据归 `validate_recipes`。
    """
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise HwCheckError(
            f"{where}必须是对象（{{…}}，字段 read.expressions / read.items），"
            f"收到 {raw!r}"
        )
    items = raw.get("items")
    if items is not None:
        if not isinstance(items, list):
            raise HwCheckError(
                f"{where}的 read.items 必须是数组，收到 {items!r}")
        out: list[RecipeRead] = []
        for item in items:
            if not isinstance(item, dict):
                raise HwCheckError(
                    f"{where}的 read.items 每一条必须是 {{expression, unit}} 对象，"
                    f"收到 {item!r}"
                )
            expression = item.get("expression")
            if not isinstance(expression, str) or not expression.strip():
                raise HwCheckError(
                    f"{where}的 read.items[].expression 必须是非空字符串，"
                    f"收到 {expression!r}"
                )
            unit = item.get("unit", "")
            if not isinstance(unit, str):
                raise HwCheckError(
                    f"{where}的 read.items[].unit 必须是字符串，收到 {unit!r}")
            out.append(RecipeRead(expression=expression.strip(), unit=unit.strip()))
        return tuple(out)
    expressions = _segment_strings(
        raw, "expressions", where, field="read.expressions")
    return tuple(RecipeRead(expression=text) for text in expressions)


def _parse_section(slug: str, platform: str, data: Any, source: str) -> RecipeSection:
    """一条配方 → RecipeSection（**形状**判据；函数名判据归 validate_recipes）。"""
    if not isinstance(data, dict):
        raise HwCheckError(
            f"{RECIPE_FILENAME} 里 {slug!r} 的 {platform} 配方必须是对象（{{…}}），"
            f"收到 {data!r}"
        )
    unknown = sorted(set(data) - set(_SEGMENTS) - {"init_expect"})
    if unknown:
        raise HwCheckError(
            f"{RECIPE_FILENAME} 里 {slug!r} × {platform} 有未定义字段："
            + "、".join(unknown)
            + f"（合法段：{'、'.join(_SEGMENTS)}）"
        )
    where = _where(slug, platform, "", source)
    prereq = _segment_strings(
        data.get("prereq"), "calls", f"{where}的前置调用段", field="prereq.calls")
    init = _segment_strings(
        data.get("init"), "calls", f"{where}的初始化段", field="init.calls")
    read = _parse_read(f"{where}的读数展示段", data.get("read"))
    note = _segment_strings(
        data.get("note"), "lines", f"{where}的平台说明段", field="note.lines")

    init_expect = ""
    raw_expect = data.get("init_expect", "")
    if raw_expect is not None:
        if not isinstance(raw_expect, str):
            raise HwCheckError(
                f"{where}的初始化段 init_expect 必须是字符串，收到 {raw_expect!r}"
            )
        init_expect = raw_expect.strip()
    if init_expect and not init:
        raise HwCheckError(
            f"{where}的初始化段 init_expect 有值（{init_expect!r}）却没有 init 调用"
            "——没有可判的返回值，请补上初始化调用或清空 init_expect"
        )

    probe: RecipeProbe | None = None
    raw_probe = data.get("probe")
    if raw_probe is not None:
        probe_where = f"{where}的通信探头段"
        calls = _segment_strings(
            raw_probe, "calls", probe_where, field="probe.calls", required=True)
        expect = ""
        raw = raw_probe.get("expect") if isinstance(raw_probe, dict) else None
        if raw is not None:
            if not isinstance(raw, str):
                raise HwCheckError(
                    f"{probe_where}的 probe.expect 必须是字符串，收到 {raw!r}"
                )
            expect = raw.strip()
        # expect 缺省 = **只做动作不判通断**（如让 OLED 显示一行"我活着"当肉眼
        # 现象）：探头段仍然有意义（那一节确实驱动了它），但板上不打 OK/FAIL
        # ——不假装测过。写了 expect 就必须是能比的东西（validate_recipes 另判）。
        probe = RecipeProbe(calls=calls, expect=expect)

    console: RecipeConsole | None = None
    raw_console = data.get("console")
    if raw_console is not None:
        console_where = f"{where}的控制台命令段"
        if not isinstance(raw_console, dict):
            raise HwCheckError(
                f"{console_where}必须是对象（{{…}}，字段 console.command），"
                f"收到 {raw_console!r}"
            )
        raw_command = raw_console.get("command")
        if not isinstance(raw_command, str) or not raw_command:
            raise HwCheckError(
                f"{console_where}缺少必填字段 console.command"
                f"（单个字符），收到 {raw_command!r}"
            )
        command = raw_command.strip()
        if len(command) != 1:
            raise HwCheckError(
                f"{console_where}的 console.command 必须是**单个字符**，"
                f"收到 {raw_command!r}（命令循环按字符分派，多字符命令没人认得出）"
            )
        description = ""
        raw_desc = raw_console.get("description", "")
        if raw_desc is not None:
            if not isinstance(raw_desc, str):
                raise HwCheckError(
                    f"{console_where}的 console.description 必须是字符串，"
                    f"收到 {raw_desc!r}"
                )
            description = raw_desc.strip()
        console = RecipeConsole(command=command, description=description)

    section = RecipeSection(
        slug=slug, platform=platform, prereq=prereq, init=init,
        init_expect=init_expect, probe=probe, read=read, console=console,
        note=note, source=source,
    )
    if not section.usable:
        raise HwCheckError(
            f"{where}的六段全空：空壳配方不是「专精」——它会让学生以为这件被测过。"
            "要么补齐六段里至少一段，要么把这一条删掉（那件走通用降级）"
        )
    return section


def parse_recipes(data: Any, *, source: str = "") -> dict[str, dict[str, RecipeSection]]:
    """配方 JSON 对象 → `{slug: {platform: RecipeSection}}`（纯函数，内存直测）。

    只判形状（键 / 段 / 值类型）；**函数名判据在 `validate_recipes`**——它需要
    模块库的接口清单，是另一个输入。两件事分开，形状测试就不必造库。
    """
    if not isinstance(data, dict):
        raise HwCheckError(
            f"{RECIPE_FILENAME} 必须是一个对象（{{slug: {{平台: 配方}}}}），"
            f"收到 {type(data).__name__}"
        )
    out: dict[str, dict[str, RecipeSection]] = {}
    for slug, platforms in data.items():
        if not isinstance(slug, str) or not slug:
            raise HwCheckError(f"{RECIPE_FILENAME} 的模块键必须是非空字符串：{slug!r}")
        if slug.startswith("_"):
            continue  # `_` 开头 = 文件内说明（JSON 没有注释语法），不是模块键
        if not isinstance(platforms, dict):
            raise HwCheckError(
                f"{RECIPE_FILENAME} 里 {slug!r} 的条目必须是 {{平台: 配方}} 对象，"
                f"收到 {platforms!r}"
            )
        for platform, section in platforms.items():
            if platform not in KNOWN_PLATFORMS:
                known = "、".join(sorted(KNOWN_PLATFORMS))
                raise HwCheckError(
                    f"{RECIPE_FILENAME} 里 {slug!r} 的平台键 {platform!r} 不在词表内"
                    f"（已注册的平台：{known}）"
                )
            out.setdefault(slug, {})[platform] = _parse_section(
                slug, platform, section, source
            )
    return out


def _calls_in(expression: str) -> tuple[str, ...]:
    """C 表达式里出现的调用名（**小写或下划线开头**的标识符紧跟 `(`）。

    判据刻意窄一点：类型转换（`(uint8_t)x`）与全大写宏名不算"调用"——它们在
    接口清单里通常是 `#define`，由 `_bare_names` 那条更宽的路径覆盖。
    """
    out: list[str] = []
    for match in _IDENT_RE.finditer(expression):
        name = match.group(0)
        if not (name[0].islower() or name[0] == "_"):
            continue
        if expression[match.end():match.end() + 1] == "(" and name not in out:
            out.append(name)
    return tuple(out)


def _bare_names(expression: str) -> tuple[str, ...]:
    """C 表达式里的标识符（含宏名 / 常量名）——期望值这类短表达式用。"""
    return tuple(dict.fromkeys(_IDENT_RE.findall(expression)))


# 读数表达式里允许出现的 C 关键字 / 字面量（判据只看"名字"是否可知，
# 这些是语言本身的东西，不在任何头文件里）
_C_KEYWORDS = frozenset({
    "sizeof", "int", "char", "long", "short", "unsigned", "signed", "void",
    "const", "volatile", "static", "uint8_t", "uint16_t", "uint32_t",
    "int8_t", "int16_t", "int32_t", "float", "double", "bool", "true", "false",
    "NULL",
})


# 对象宏（`#define LED_CHANNEL_COUNT 3`）：生成门禁的 `_decl_or_macro_names` 只收
# 「类函数宏」与带类型的声明，**对象宏名不在它的清单里**——但配方读数列里最自然的
# 写法恰恰是这种常量（如 `LED_CHANNEL_COUNT`）。所以配方侧的清单要把它并进来，
# 否则"配方写了一个真实存在的常量"会被误判成拼错（本单真机上撞到过）。
_OBJECT_MACRO_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)", re.MULTILINE)


def _define_names(headers: Sequence[tuple[str, str]]) -> frozenset[str]:
    """头文件里全部 `#define` 名（对象宏 + 类函数宏）——配方侧的补充清单。

    ⚠ 有意**不剥注释**再扫：剥注释会把"注释里提到的宏"也算进来（漏判），而
    多算进来的是本模块/母版头里真实写过的东西，风险方向正确。实测影响面很小
    （母版头注释里出现的宏名本就寥寥），换来的是不误伤真实存在的常量。
    """
    out: set[str] = set()
    for _rel, text in headers:
        out.update(_OBJECT_MACRO_RE.findall(text))
    return frozenset(out)


def _is_literal(expect: str) -> bool:
    return bool(_NUMBER_RE.match(expect))


# C 字符串字面量的转义表（反斜杠与引号必须先转，否则会把后面的字节解释错）
_C_ESCAPES = {"\\": "\\\\", '"': '\\"'}


def escape_c_string(text: str) -> str:
    """C 字符串字面量内容 → **纯 ASCII** 源码写法（非 ASCII 一律 `\\xNN` 转义）。

    ## 为什么必须转义（工单 module-hwcheck/04 的真机判例，别改成原样输出）

    stm32 的 Keil ARMCC 5.06 **默认按本地多字节代码页（本机 GBK）解析源文件**：
    中文字面量以特定字节收尾时（如「通过：」的 `EF BC 9A`），最后那个字节 0x9A
    会被当成 GBK 前导字节、把收尾引号 0x22 当它的尾字节一起吞掉 →
    `#8: missing closing quote`，整份 main.c 编不过（实测 22 error）。这是
    spec 判据「stm32 UV4 编译绿」一票否决的问题。

    两条出路都真机量过（`.scratch/module-hwcheck/probe-04-armcc-utf8.py` /
    `-flags.py` / `-escaped-literals.py`）：

    * 给工程加 `--locale=english` 编译开关 → 0 error（但要改**母版工程**的
      编译选项，那是跨平台共享面）；
    * **把非 ASCII 转义成 UTF-8 字节** → 0 error，源码纯 ASCII、产出的字节与
      原文逐字节相等（本函数）。

    取后者：不动母版、不依赖任何编译器的本地化设置，上网后学生看到的还是同一个
    字（串口按 UTF-8 解就是中文）。转义只换写法，不改字。
    """
    out: list[str] = []
    for char in text:
        if char in _C_ESCAPES:
            out.append(_C_ESCAPES[char])
        elif ord(char) < 128:
            out.append(char)
        else:
            out.extend(f"\\x{byte:02x}" for byte in char.encode("utf-8"))
    return "".join(out)


def c_string(text: str) -> str:
    """带引号的 C 字符串字面量（转义单源——渲染产物里每个字面量都走它）。"""
    return f'"{escape_c_string(text)}"'


def validate_recipes(
    recipes: Mapping[str, Mapping[str, RecipeSection]],
    manifests: Sequence[ModuleManifest],
    interfaces: Mapping[str, frozenset[str] | set[str]],
) -> None:
    """引用校验（**本单的核心守卫**）：键必须是库内 slug、必须有该平台条目、
    引用的函数名必须在该模块该平台的头文件接口清单内。任一不满足 → 中文大声失败。

    `interfaces` = `{slug: 该模块该平台头文件里的名字集合}`（函数 + 函数式宏，
    与生成门禁同一份提取：`skeleton.extract_header_functions`；由
    `interface_names` 装配）。两条刻意的宽免：

    * **接口集为空的 slug 不判**——`files: []` 的平台条目（实现内嵌母版）
      在拿不到母版头时清单为空（如只用模块库、没配母版库的场景）。此时判不了，
      就不假装判过、也不冤枉好配方（真实库装配点会并进母版头，判据完整）；
    * **`prereq` 段不过这道判据**——见 `RecipeSection.prereq` 的说明（跨模块
      占位调用归工单 05）。
    """
    by_slug = {manifest.slug: manifest for manifest in manifests}
    for slug, platforms in recipes.items():
        manifest = by_slug.get(slug)
        if manifest is None:
            raise HwCheckError(
                f"{RECIPE_FILENAME} 里的模块 {slug!r} 不在模块库内"
                "——配方只能给库内真实存在的模块写（库删了模块而配方没跟上，"
                "这里当场红，不静默丢掉那一条）"
            )
        for platform, section in platforms.items():
            if manifest.platforms.get(platform) is None:
                raise HwCheckError(
                    f"{RECIPE_FILENAME} 里 {slug!r} 写了 {platform} 的配方，"
                    f"但该模块没有 {platform} 平台条目"
                )
            known = set(interfaces.get(slug, frozenset()))
            if not known:
                # 这个 slug 拿不到任何接口（模块实现内嵌母版 + 调用方没给母版头）
                # ——判不了就不判，不冤枉好配方、也不放过有清单的（真实库装配点
                # 会并进母版头，那条路上判据是完整的）。
                continue
            for segment, expressions in (
                ("init", section.init),
                # 读数表达式整条过判据（不只是"像调用"的部分）：裸常量同样要
                # 在接口清单里——本单 pilot 的 read 恰好全是裸宏，只查调用会
                # 让 `OLED_RES_128X64` 这种"另一个平台才有的常量"漏过去，
                # 一路漏到编译期（评审实测：stm32 侧 #20 undefined）。
                ("read", [item.expression for item in section.read]),
                ("probe", section.probe.calls if section.probe else ()),
            ):
                for expression in expressions:
                    for name in _calls_in(expression):
                        if name not in known:
                            raise HwCheckError(
                                f"{_where(slug, platform, segment, section.source)}"
                                f"引用了不存在的接口 {name!r}（表达式：{expression}）"
                                f"——该模块 {platform} 侧的头文件里没有这个名字，"
                                "请改用真实接口（配方写错就该当场红，不学骨架兜底"
                                "把它改成注释）"
                            )
                    if segment != "read":
                        continue
                    for name in _bare_names(expression):
                        if name in _C_KEYWORDS or name in known:
                            continue
                        raise HwCheckError(
                            f"{_where(slug, platform, segment, section.source)}"
                            f"的读数表达式 {expression!r} 里有找不到的名字 {name!r}"
                            f"——它既不是 C 关键字、也不在该模块 {platform} 侧的接口"
                            "清单里（拼错的宏名 / 另一个平台才有的常量都会在这里被"
                            "拦下，不然要漏到编译期）"
                        )
            for expect, segment in (
                (section.init_expect, "init"),
                (section.probe.expect if section.probe else "", "probe"),
            ):
                if not expect or _is_literal(expect):
                    continue
                for name in _bare_names(expect):
                    if name not in known:
                        raise HwCheckError(
                            f"{_where(slug, platform, segment, section.source)}的"
                            f" expect 期望值 {expect!r} 既不是数字字面量、也不是"
                            f"该模块接口清单里的常量（未找到 {name!r}）"
                        )


def load_recipes(
    module_library_dir: Path | str,
    manifests: Sequence[ModuleManifest],
    interfaces: Mapping[str, frozenset[str] | set[str]] | None = None,
    *,
    recipe_path: Path | str | None = None,
) -> dict[str, RecipeCatalog]:
    """读库内配方文件 → 校验 → `{slug: RecipeCatalog}`。

    三种结局（与"缺件 / 坏件"的区分一致，见模块头）：

    * 文件不在 → 空字典（老库照常生成，全走通用降级）；
    * 文件在但 JSON 非法 / 形状不对 / 引用不存在的接口 → `HwCheckError` 中文；
    * 正常 → 逐条 RecipeSection，按 slug 归成目录。

    `interfaces` 缺省 = 只判形状不查函数名（文档 / 探针脚本够用）；检测页与
    生成侧**必须**传（那是本单的守卫）。

    `recipe_path` 缺省 = 按库根推（`recipe_library_path`）；显式给 = 读另一个
    文件（测试注入坏配方时用——**不改真库的那一份**，并行跑用例才不会被别的
    worker 读到半截，本仓库 2026-09-19 踩过同款）。
    """
    path = Path(recipe_path) if recipe_path is not None else recipe_library_path(
        module_library_dir
    )
    if not path.is_file():
        return {}
    source = str(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HwCheckError(f"{RECIPE_FILENAME} 读不出来（{path}）：{exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HwCheckError(
            f"{RECIPE_FILENAME} 不是合法 JSON（{path}，第 {exc.lineno} 行）：{exc.msg}"
        ) from exc
    parsed = parse_recipes(data, source=source)
    if interfaces is not None:
        validate_recipes(parsed, manifests, interfaces)
    return {
        slug: RecipeCatalog(slug=slug, sections=sections)
        for slug, sections in parsed.items()
    }


def interface_names(
    manifests: Sequence[ModuleManifest],
    module_library_dir: Path | str,
    platform: str,
    master_headers: Sequence[tuple[str, str]] = (),
) -> dict[str, frozenset[str]]:
    """`{slug: 该模块在**该平台**能调到的名字}`——配方引用校验的输入（单源）。

    判据与生成门禁**同一套**（`skeleton.format_interface_blocks` +
    `extract_header_functions`）：骨架自检说"这个调用存在"，配方校验就必须认同一套，
    否则会出现"配方过了校验、生成门禁却说未定义"的错位。

    两份来源缺一不可：

    * **模块自己的头文件**（manifest 平台条目声明的 .h）；
    * **母版头**（`master_headers` = 生成语料 `ModuleCorpus.master_headers`：
      `[ (相对路径, 文本) ]`）——`files: []` 的平台条目（实现在母版里，如 stm32
      的 led / oled / delay）**一个模块头都没有**，它们能调的函数全在母版头里；
      不并进来的话，stm32 的 led 配方会被误判成"引用了不存在的接口"。
      mspm0 母版无 .h，并入为空、无副作用。

    母版头对每个 slug 都并入（不区分模块）：母版库是工程级共享的（`headfile.h`
    聚合 ml_* 全部接口）——与生成门禁的判定范围一致，不会放过"门禁也认"的名字。

    另并入**对象宏名**（`#define LED_CHANNEL_COUNT 3` 这种，`_define_names`）：
    生成门禁的提取只收「类函数宏 + 带类型的声明」，而配方读数里最自然的写法的
    恰恰是对象宏——不并进来，"写了一个真实存在的常量"会被误判成拼错。
    """
    from .skeleton import extract_header_functions, format_interface_blocks

    master_names = frozenset(
        extract_header_functions(
            format_interface_blocks(
                [("母版", rel, text) for rel, text in master_headers]
            )
        )
    ) | _define_names(list(master_headers))
    library = Path(module_library_dir)
    out: dict[str, frozenset[str]] = {}
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        headers: list[tuple[str, str, str]] = []
        for rel in entry.files:
            if not rel.endswith(".h"):
                continue
            path = library / manifest.slug / rel
            if path.is_file():
                headers.append(
                    (manifest.slug, rel,
                     path.read_text(encoding="utf-8", errors="replace"))
                )
        out[manifest.slug] = (
            frozenset(extract_header_functions(format_interface_blocks(headers)))
            | master_names
            | _define_names([(rel, text) for _slug, rel, text in headers])
        )
    return out


def resolve_sections(
    platform: str,
    devices: Sequence[str],
    recipes: Mapping[str, RecipeCatalog],
    manifests: Sequence[ModuleManifest],
) -> tuple[RecipeSection, ...]:
    """选中的器件 → 要渲染的小节（判据单源：顺序走既有 bring-up 排序）。

    顺序与工程 README 的「验证顺序清单」**同一函数**
    （`readme.sort_verification_order`）——检测程序里的次序与 README 那张清单
    不一致，学生会照着一个做、被另一个打脸。没有配方的器件**不出小节**
    （本单不做通用降级，归工单 07）。
    """
    wanted = [
        slug for slug in dict.fromkeys(devices)
        if (catalog := recipes.get(slug)) is not None
        and catalog.for_platform(platform) is not None
    ]
    if not wanted:
        return ()
    by_slug = {manifest.slug: manifest for manifest in manifests}
    order = {
        manifest.slug: index
        for index, manifest in enumerate(
            sort_verification_order(
                [by_slug[slug] for slug in wanted if slug in by_slug]
            )
        )
    }
    sections = [recipes[slug].for_platform(platform) for slug in wanted]
    return tuple(
        sorted(
            (section for section in sections if section is not None),
            key=lambda section: (order.get(section.slug, len(order)), section.slug),
        )
    )


def unspecialized_message(slug: str) -> str:
    """「这件还没有专精配方」的页面文案（判据在配方表，文案归检测页）。

    工单 04 起检测程序**只给有配方的器件出小节**（通用降级归工单 07），所以
    页面上必须点名说清"这一件这一趟不会真测它"——不然学生会以为选了 = 测了
    （spec「不假装测过」）。
    """
    return (
        f"{slug}：这一件还没有专精配方——本版检测程序不会给它出检测小节"
        "（通用降级在后续工单里做）。它仍然会接进工程并出现在接线表里，"
        "但板上不会对它做任何判定。"
    )


def render_recipe_section(
    section: RecipeSection, report: dict[str, Any] | None = None
) -> list[str]:
    """一件器件的检测小节 → 缩进好的 C 语句（纯函数，可逐字断言）。

    形态（确定性）：注释块（哪一件 / 平台说明 / 专精声明）→ 小节头
    `hwcheck_section` → 前置调用 → 初始化 → 通信探头 → 读数回显 → 判定记账
    （`hwcheck_verdict*`，结尾汇总数得出来"真测了几件"）。

    **两级判定**（spec 判据三层里的第②层；判定都在板上算）：

    * 判据 = 配方写了 `init_expect`（初始化返回值约定）或 `probe.expect`
      （通信探头期望值）：**判定在板上算**（比较式落进渲染出的 C），探
      不到就打 FAIL 并**直接 return**——不通就不再打一堆无意义读数。
    * 判不了（`void` 初始化没有返回值可判 / 纯输出件没有可读寄存器，如
      led / oled）= 如实打 `hwcheck_verdict_probe_none` + "只看现象"，
      **不算通过**。`probe.calls` 允许只做动作、不带期望值（如让 OLED
      显示一行"我活着"作为肉眼现象），此时仍不打判定。

    ⚠ **字面量一律经 `c_string` 转义**（非 ASCII → `\\xNN`）：ARMCC 5.06 按本地
    代码页解析源文件，原样中文字面量会让整份 main.c 编不过（真机判例见
    `escape_c_string` 的 docstring）。注释里保留中文——那是给人读的，不影响解析。

    `report` 非空时被填进这一节的观测：`slug` / `verdict`（带判定时的 ok）、
    `probe`（有没有带期望值的探头）/ `trouble`（排查指引）。渲染本身不打印、
    不读盘。
    """
    probe = section.probe
    judged_probe = probe is not None and bool(probe.expect)
    judged_init = bool(section.init_expect)
    out: list[str] = [
        f"    /* ---- {SECTION_TAG} {section.slug}：按库内配方测这一件 ---- */",
    ]
    for note in section.note:
        out.append(f"    /* 平台说明：{note} */")
    out.append("    /* 专精件：这一节真的会驱动它 / 读它（未专精件本版不出小节）。 */")
    out.append(f"    hwcheck_section({c_string(f'{SECTION_TAG} {section.slug}')});")

    if judged_init or judged_probe:
        out.append("    int r;")
    for call in section.prereq:
        out.append(f"    {call};")
    for call in section.init:
        out.append(f"    r = {call};" if judged_init else f"    {call};")
    if judged_init:
        expected = section.init_expect
        out.append(f"    hwcheck_report({c_string('  初始化：')});")
        out.append(
            "    hwcheck_report((r == "
            f"{expected}) ? {c_string('OK')} : {c_string('FAIL')});"
        )
        out.append(
            f"    if (r != {expected}) {{ hwcheck_detail("
            + c_string("初始化没有按接口约定返回期望值——先查接线与供电，再查驱动")
            + "); }"
        )
        out.append(
            f"    hwcheck_verdict((r == {expected}), "
            + c_string(f"{section.slug}：初始化没有按接口约定返回期望值")
            + ");"
        )
    elif section.init:
        # 配了初始化、却没写期望值（如 void led_init 没有返回值可判）：
        # 如实说"调了、这一件不判返回值"，不编一个比较式出来
        out.append(f"    hwcheck_report({c_string('  初始化：')});")
        out.append(f"    hwcheck_report({c_string('已调用（本件不判返回值）')});")
        out.append("    hwcheck_newline();")
    if probe is not None:
        for call in probe.calls:
            out.append(f"    r = {call};" if judged_probe else f"    {call};")
        if judged_probe:
            expected = probe.expect
            out.append(f"    hwcheck_report({c_string('  通信探头：')});")
            out.append(
                "    hwcheck_report((r == "
                f"{expected}) ? {c_string('OK')} : {c_string('FAIL')});"
            )
            out.append(f"    if (r != {expected})")
            out.append("    {")
            out.append(
                "        hwcheck_detail("
                + c_string("通信失败：先查供电 / 上拉 / 地址 / 线序，再查驱动")
                + ");"
            )
            out.append(
                "        hwcheck_verdict(0, "
                + c_string(
                    f"{section.slug}：通信失败（先查供电 / 上拉 / 地址 / 线序）"
                )
                + ");"
            )
            out.append("        return;   /* 不通就不再打一堆无意义读数 */")
            out.append("    }")
            out.append(
                f"    hwcheck_verdict(1, {c_string(f'{section.slug}：通信正常')});"
            )
    if not judged_probe:
        out.append(
            "    hwcheck_verdict_probe_none("
            + c_string(
                f"{section.slug}：这一件没有读取型探头，"
                "通断无法判定——只看现象是否出现"
            )
            + ");"
        )
        out.append(
            "    hwcheck_detail("
            + c_string(
                "本件没有可读的身份 / 状态寄存器，板上判不了通断："
                "请对照检测页清单看现象（灯闪 / 屏亮）"
            )
            + ");"
        )

    for item in section.read:
        label = item.expression[:60] + ("…" if len(item.expression) > 60 else "")
        out.append(f"    hwcheck_report({c_string(f'  {label} = ')});")
        out.append(f"    hwcheck_report_int({item.expression});")
        if item.unit:
            out.append(f"    hwcheck_report({c_string(f' {item.unit}')});")
        out.append("    hwcheck_newline();")

    if report is not None:
        report["slug"] = section.slug
        report["probe"] = judged_probe
        # 渲染期能给的就只有"这一件**可能**报什么错、错了先查哪里"——判定结果
        # （ok / fail）要到板上才算得出来，所以这里**不写 verdict**：写了也只有
        # 一个恒定值，汇总侧照它分支就会是一条永不触发的死路（评审抓到的坑）。
        report["trouble"] = (
            f"{section.slug}：通信失败（先查供电 / 上拉 / 地址 / 线序）"
            if judged_probe
            else f"{section.slug}：没有读取型探头，只看了现象"
        )
    out.append("")
    return out


def render_recipe_summary(reports: Sequence[Mapping[str, Any]]) -> list[str]:
    """结尾汇总（缩进好的 C 语句）：三档分开数（板上算）+ 先列排查线索。

    **不许把没探头的算进"通过"**（spec 判据三层：第③层只是回显，不做板上阈值
    判决）——所以三档分开数在 C 侧（`hwcheck_summary`）。

    "万一判失败先查哪里"的那几行**只在有带判定的小节时才印**：一件判据都没有
    的形态（如只有 led）印出来纯是噪声——判定在板上产生，渲染期不该抢在结果
    前面把"通信失败"喊出来（评审抓到的坑：探头判过的件也会被先打一句失败话术）。
    没有专精件时如实说一句，不渲染一个"0 件通过"的假汇总。
    """
    out: list[str] = ["    /* ---- 汇总：这一趟到底测了什么 ---- */"]
    if not reports:
        out.append("    /* 这一趟没有专精件：只确认板子与烧录链路是活的。 */")
        out.append("    hwcheck_summary();")
        return out
    if any(item.get("probe") for item in reports):
        for trouble in dict.fromkeys(
            str(item.get("trouble") or "")
            for item in reports
            if item.get("probe")
        ):
            if not trouble:
                continue
            out.append(f"    hwcheck_detail({c_string(trouble)});")
    out.append("    hwcheck_summary();")
    return out
