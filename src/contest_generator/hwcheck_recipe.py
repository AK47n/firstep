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
from .master_store import master_project_dir
from .platforms import KNOWN_PLATFORMS
from .readme import sort_verification_order
from .treewalk import iter_project_files

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
    "load_library_recipes",
    "load_recipes",
    "local_names",
    "parse_includes",
    "parse_locals",
    "parse_recipes",
    "platform_header_names",
    "recipe_library_path",
    "render_recipe_section",
    "render_recipe_summary",
    "resolve_sections",
    "sections_payload",
    "validate_recipes",
]

# 配方文件名（跟随模块库根的平级兄弟，见模块头「落点」）
RECIPE_FILENAME = "hwcheck_recipes.json"

# 专精小节的标题尾巴：**用户一眼看出"这件真测了"**（票面验收线）。未专精件
# 由工单 07 的通用降级渲染，标题不带这个标记——改标记只改这一处。
SECTION_TAG = "[专精]"

# 六段（spec 定义）+ 工单 05 补的两项：`locals`（局部变量声明，见
# RecipeSection.locals）与 `include`（这一节的调用要 include 哪些头文件，见
# RecipeSection.include）。缺段 = 该件不支持该项，一律合法；全缺 = 空壳。
_SEGMENTS = ("include", "locals", "prereq", "init", "probe", "read", "console", "note")

# 段 → 中文名（报错文案里点名"哪一段"，用学生看得懂的说法）
_SEGMENT_NAMES = {
    "include": "头文件",
    "locals": "局部变量声明",
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
    """串口控制台命令（`console` 段）：一个**首选**字符 + 若干**候选**字符 + 一句说明。

    单字符是**硬要求**（库内既有的 `r` / `y` / `g` / `o` / `b<N>` 都是单字符，
    命令循环按字符分派）；说明进检测页与回显。

    `candidates`（工单 hwcheck-specialize/01）＝ **首选被别的器件占用时按顺序让位
    到哪几个字符**。为什么要它：命令空间一共 31 个可用字符（字母数字除去保留字
    `r/y/g/o/b/?`），专精件一多，"首字母记法"必然撞车（`sht20` / `sht30` /
    `sgp30` / `servo` / `sr04` 都想用 `s`），而撞车的后果是**构建期 400**——
    学生勾两件传感器就生成不出来。给一件声明候选，撞车时它自己让位，学生看到的
    仍是"一件一个字符"。候选只在**首选不可用时**才轮到，顺序就是声明顺序
    （确定性：同一选中集恒定同一结果）。

    **本类只管形状**；那张"谁能用哪个字符"的表（保留字 / 让位 / 形状加严）与
    C 侧分派都在 `hwcheck_console.py`（`build_console_table` / `console_payload`
    / `render_console_runtime`，工单 06 落地）——配方数据与"命令空间"是两件事，
    分开放，配方的形状判据就不必知道库内既有命令叫什么。
    """

    command: str
    description: str = ""
    candidates: tuple[str, ...] = ()


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

    字段顺序按 `_SEGMENTS`（`include` 在最前，渲染时也是先 include 再声明再动作）。
    工单 05 补的两个字段：

    `include` ＝ **这一节的调用要 include 哪些头文件**（`ml_mpu6050.h` /
    `mpu_port.h` / `ml_i2c.h`）。为什么放在配方而不是让框架自己推：① 检测程序
    （它就是"应用"）直接调模块函数，而框架那套固定 include 只覆盖通道与心跳
    （led / delay / oled / debug_uart）——器件模块一个都不在里面，真机口径下
    `main.c` 会报一串 `#223-D function declared implicitly` 与
    `#20 identifier undefined`（本单实测 7 error）；② 前置调用天生跨模块
    （stm32 侧要先调母版 `I2C_Init()`，头在 `ml_i2c.h`），从"本件的清单"推不出
    另一个模块的头；③ 哪些头是这一节真正的依赖，写配方的人知道，从 `files`
    里"全收 .h"是猜（会把 DMP 固件表之类无关头一起拉进 main.c）。

    `locals` ＝ **这一节自己要声明的局部变量**，每条是一句 C 声明
    （`float pitch = 0`）。为什么它必须是**小节级**而不是放进 `read` 段：
    声明的作用域要盖住 `probe`——mspm0 的官方 DMP 探头本身就是
    `DMP_Read_Data(&pitch, &roll, &yaw)`（既证通信通、又把角度搬进变量），
    变量得先声明出来才读得回来。渲染时它们排在最前面（紧跟 `int r;`）。

    这一项也是"配方写 C"这条既定决策的延续（同 spec「调用什么写成 C 表达式
    字符串」的理由）：结构化描述只会重新发明一遍 C 的声明语义。判据刻意窄——
    只认 `类型 名字 [= 数字]` 形的声明（`parse_locals`），名字因此能被静态看出来
    并进引用校验的白名单。
    """

    slug: str
    platform: str
    include: tuple[str, ...] = ()
    locals: tuple[str, ...] = ()
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


# 局部变量声明的**形状**（工单 05）：`类型 名字` 或 `类型 名字 = 数字字面量`。
# 判据刻意窄——多词类型（`unsigned int` / `const float`）收，一次声明多个变量
# （`float a = 0, b = 0`）、数组、函数指针、带副作用的初始化式**一律不收**：
# 名字必须能静态看出来（它要进引用校验的白名单），这一点比"什么 C 都写得下"重要。
# **类型与名字之间必须是空白**（`\s+`，不是 `\s*`）：放宽成 `\s*` 的话裸类型串
# `"int"` 会被拆成类型 `i` + 名字 `nt`——"只有类型、忘了写名字"这种手滑就漏过去了。
_LOCAL_DECL_RE = re.compile(
    r"^(?P<type>[A-Za-z_][\w\s]*?)\s+\*?\s*(?P<name>[A-Za-z_]\w*)"
    r"(?:\s*=\s*(?P<init>[^;]+?))?\s*$"
)


def parse_locals(
    segment: Any, where: str, *, field: str = "locals.declarations"
) -> tuple[str, ...]:
    """`locals` 段 → 声明字符串元组（纯函数；形状判据，类型是不是真类型归校验）。

    `{declarations: ["float pitch = 0", …]}`；缺段 = 这一件不需要自己声明变量。
    """
    declarations = _segment_strings(segment, "declarations", where, field=field)
    seen: set[str] = set()
    for declaration in declarations:
        match = _LOCAL_DECL_RE.match(declaration)
        if match is None:
            raise HwCheckError(
                f"{where}的 {field} 只收 `类型 名字` 或 `类型 名字 = 数字` 形的声明"
                f"（一次声明一个变量、初值只能是数字字面量），收到 {declaration!r}"
                f"——判据要能静态看出变量名，它进引用校验的白名单"
            )
        name = match.group("name")
        if name in _C_KEYWORDS:
            raise HwCheckError(
                f"{where}的 {field} 里 {declaration!r} 的变量名 {name!r} 是 C 关键字"
            )
        if name in seen:
            raise HwCheckError(
                f"{where}的 {field} 里 {name!r} 声明了两次"
                "（同一节里重复声明同名变量，编译期才会发现）"
            )
        init = (match.group("init") or "").strip()
        if init and not _is_literal(init):
            raise HwCheckError(
                f"{where}的 {field} 里 {declaration!r} 的初值必须是数字字面量，"
                f"收到 {init!r}（初值写别的会把名字藏进表达式里，白名单就失灵了）"
            )
        seen.add(name)
    return declarations


def local_names(declarations: Sequence[str]) -> frozenset[str]:
    """声明字符串 → 变量名集合（引用校验用；形状已由 `parse_locals` 判过）。"""
    out: set[str] = set()
    for declaration in declarations:
        match = _LOCAL_DECL_RE.match(declaration)
        if match is not None:
            out.add(match.group("name"))
    return frozenset(out)


def local_type_names(declarations: Sequence[str]) -> tuple[str, ...]:
    """声明字符串里出现的**类型词**（`unsigned int v` → `unsigned`/`int`）——校验用。"""
    out: list[str] = []
    for declaration in declarations:
        match = _LOCAL_DECL_RE.match(declaration)
        if match is None:
            continue
        for word in _IDENT_RE.findall(match.group("type")):
            if word not in out:
                out.append(word)
    return tuple(out)


def parse_includes(
    segment: Any, where: str, *, field: str = "include.headers"
) -> tuple[str, ...]:
    """`include` 段 → 头文件名元组（纯函数；形状判据，能否解析归引用校验）。

    `{headers: ["ml_mpu6050.h", …]}`；缺段 = 这一节只靠框架那套固定 include
    （如 led / oled：它们由 led_instances.h / headfile.h 覆盖）。
    """
    headers = _segment_strings(segment, "headers", where, field=field)
    for header in headers:
        if not header.endswith(".h") or "/" in header or "\\" in header:
            raise HwCheckError(
                f"{where}的 {field} 只收**头文件名**（形如 `ml_mpu6050.h`，不带"
                f"目录、必须以 .h 结尾），收到 {header!r}"
                "——include 路径由工程的 IncludePath 决定，配方不指定目录"
            )
    return headers


def platform_header_names(
    manifests: Sequence[ModuleManifest],
    platform: str,
    master_headers: Sequence[tuple[str, str]] = (),
) -> frozenset[str]:
    """该平台工程里**可能出现的头文件名**（小写基名）——`include` 段的判据面。

    两份来源，与生成门禁的 include 解析门（`generator._check_unresolved_includes`）
    **方向一致、口径不同**：门禁问的是"这个 include 在**建出来的那个工程**里解析
    得到吗"（own_dir 兄弟头 ∪ 模块目录 ∪ 搜索目录 ∪ 豁免），这里问的是"库 / 母版
    声明过这个名字吗"（不读盘，只看 manifest 的 files 与母版头的路径）——
    ① 库内每个模块该平台条目声明的 `.h` 基名；② 母版树的 `.h` 基名。

    这条宽松（只看声明）是刻意的：真实可解析性由生成门禁兜底
    （`UnresolvedIncludeError`，中文点名那个头），两处都在，判错的方向才安全。
    """
    names: set[str] = set()
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for rel in entry.files:
            if rel.lower().endswith(".h"):
                names.add(Path(rel).name.lower())
    for rel, _text in master_headers:
        if rel.lower().endswith(".h"):
            names.add(Path(rel).name.lower())
    return frozenset(names)


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


def _parse_console_candidates(
    raw: Any, where: str, command: str
) -> tuple[str, ...]:
    """`console.candidates` → 候选字符元组（纯函数；**形状**判据，保序）。

    判据刻意与 `console.command` 同款：每个候选必须是**单个字符**（命令循环按
    字符分派），多字符 / 空串 / 非字符串一律点名字段大声失败——静默丢掉一个写错
    的候选，表现是"这一件老是撞车"，查不出是哪一行写坏了。

    缺省 = 没有候选（空元组）：老配方**逐字兼容**。与首选重复（或候选之间重复）
    不算错，只是冗余——分配时按归一形态去重，不会出现"同一个字符试两遍"。
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise HwCheckError(
            f"{where} 必须是字符数组（如 [\"w\", \"z\"]，首选被占用时按这个顺序"
            f"让位），收到 {raw!r}"
        )
    out: list[str] = []
    for item in raw:
        text = item.strip() if isinstance(item, str) else ""
        if len(text) != 1:
            raise HwCheckError(
                f"{where} 里的 {item!r} 不是**单个字符**——候选与首选同款判据："
                "命令循环按字符分派，多字符 / 空候选没人认得出"
            )
        if text == command or text in out:
            continue  # 首选自己 / 重复声明：冗余但合法，去重即可
        out.append(text)
    return tuple(out)


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
    include = parse_includes(
        data.get("include"), f"{where}的头文件段", field="include.headers")
    locals_ = parse_locals(
        data.get("locals"), f"{where}的局部变量声明段",
        field="locals.declarations",
    )
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
        candidates = _parse_console_candidates(
            raw_console.get("candidates"), f"{console_where}的 console.candidates",
            command,
        )
        console = RecipeConsole(command=command, description=description,
                                candidates=candidates)

    section = RecipeSection(
        slug=slug, platform=platform, include=include, locals=locals_,
        prereq=prereq, init=init,
        init_expect=init_expect, probe=probe, read=read, console=console,
        note=note, source=source,
    )
    if not section.usable:
        raise HwCheckError(
            f"{where}各段全空：空壳配方不是「专精」——它会让学生以为这件被测过。"
            "要么补齐至少一段（局部变量声明不算动作），要么把这一条删掉"
            "（那件走通用降级）"
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
    """C 表达式里出现的调用名：**紧跟 `(` 的标识符**（大小写都算，关键字除外）。

    ⚠ **大小写都收是工单 05 修的漏洞**（原先只收小写/下划线开头）。当时的理由是
    "全大写多半是 `#define`（类型转换 / 通道宏）"——但那个假设漏掉了最要命的
    一类：**官方库的函数就是大写开头的**（`DMP_Init` / `DMP_Read_Data` /
    `MPU6050_Read` / `OLED_Init`）。于是本单的核心配方里，探头的那个调用名
    **压根没过判据**——拼错一个字母也不会红，正是本单要防的"看着测了其实没测"。
    判据改成"形式"而不是"大小写"：**标识符紧跟 `(`** 才算调用，
    `(uint8_t)x` 这种强制转换（后面是 `)`）与裸宏名照旧不算。

    另跳过 C 关键字：`sizeof(x)` / `(int)(x)` 这类是语言构造，不在任何头文件里。
    """
    out: list[str] = []
    for match in _IDENT_RE.finditer(expression):
        name = match.group(0)
        if name in _C_KEYWORDS:
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


# `extern` 声明（到分号为止）——模块的**公开数据接口**也是接口。
_EXTERN_DECL_RE = re.compile(r"\bextern\b([^;{}]*);", re.MULTILINE)

# 枚举体（`enum { … }` / `typedef enum { … } T;`）与 typedef 名字：配方侧的
# 补充清单，见 `_enum_and_typedef_names`。枚举体不许跨 `;`（`enum { … }` 之后
# 才是名字），`[^};]*` 保证不会把整个头文件当成一个枚举体。
_ENUM_BODY_RE = re.compile(r"\benum\b[^;{}]*\{([^};]*)\}")
_TYPEDEF_NAME_RE = re.compile(
    r"\btypedef\b(?:[^;{}]|\{[^}]*\})*?\b([A-Za-z_]\w*)\s*;", re.DOTALL
)

# 声明里不是变量名的词：类型 / 限定词 / 存储类。判据刻意窄（只列这几类 + 下方
# `struct`/`union`/`enum` 后的标签名）：多收的仍是头文件里真实写过的标识符，
# 风险方向与 `_define_names` 一致——**宁可多认，不可冤枉真实存在的名字**。
_C_TYPE_WORDS = frozenset({
    "const", "volatile", "static", "extern", "register", "auto", "unsigned",
    "signed", "char", "short", "int", "long", "float", "double", "void",
    "struct", "union", "enum", "inline",
})
_TAG_INTRO_WORDS = frozenset({"struct", "union", "enum"})


def _extern_names(headers: Sequence[tuple[str, str]]) -> frozenset[str]:
    """头文件里 `extern` 声明的**全局量名**——配方读数会写它们。

    为什么必须有这条：`ml_mpu6050.h` 用 `extern int16_t ax, ay, az, gx, gy, gz;`
    把六轴原始值暴露给调用方（驱动 `MPU6050_GetData()` 的产出就在这几个全局量
    里），而生成门禁那套提取（`skeleton.extract_header_functions`）只收函数与
    宏——不补这一条，"配方引用了一个头文件里真实存在的全局量"会被判成拼错
    （本单实测：诊断报 `ax` 找不到，而它就在模块头里）。

    与 `_define_names` 同款：这是**配方侧的补充清单**，不动生成门禁共用的那个
    提取函数（改它会牵动门禁判据）。
    """
    out: set[str] = set()
    for _rel, text in headers:
        for body in _EXTERN_DECL_RE.findall(text):
            names = _IDENT_RE.findall(body)
            skip_next = False
            for name in names:
                if skip_next:
                    skip_next = False          # `struct int_param_s` 的标签名
                    continue
                if name in _TAG_INTRO_WORDS:
                    skip_next = True
                    continue
                if name in _C_TYPE_WORDS or name.endswith("_t"):
                    continue
                out.add(name)
    return frozenset(out)


def _header_names(headers: Sequence[tuple[str, str]]) -> frozenset[str]:
    """一份头文件列表能提供的**全部可引用名字**（配方侧白名单的补充提取器）。

    生成门禁那套 `extract_header_functions` 只管「函数声明 + 类函数宏」；配方是
    人写的 C 表达式，还会用到对象宏 / extern 全局量 / 枚举常量 / typedef 名——
    这四个补充提取器收在这里，母版头与模块头两条路径共用（加第五个只改一处）。
    """
    return _define_names(headers) | _extern_names(headers) | _enum_and_typedef_names(headers)


def _enum_and_typedef_names(
    headers: Sequence[tuple[str, str]],
) -> frozenset[str]:
    """头文件里的 **enum 常量名 + typedef 类型名**（配方侧的补充清单，工单 09）。

    为什么单独立一条：`typedef enum { ADC_Channel_0, … } ADCINx_enum;` 里的
    常量是**真实存在的接口名**，也是"通道 / 模式"这类参数最自然的写法；而生成
    门禁那套提取（函数声明 + `#define`）一个都不收。缺了它，配方会被逼着绕道
    ——stm32 的 adc 读数只能写成"整型变量 + 强转"，代价是 4 个
    `#188-D: enumerated type mixed with another type`（检测程序的验收线是
    0 error / **0 warning**）。

    枚举体**先剥注释**再取名字（`clex.strip_comments`）：枚举体里常写
    `ADC_Channel_0,  //PA0` 这种行尾注记，不剥的话注释里的词也会进白名单
    ——与 `_define_names` 的"不剥注释"不同，这里剥得起（枚举体短、注释密）。
    方向仍是**宁可多认，不可冤枉真实存在的名字**（多认的仍是头文件里真写过的）。
    """
    out: set[str] = set()
    for _rel, text in headers:
        stripped = strip_comments(text)  # 每个头只剥一次（两个正则共用）
        for body in _ENUM_BODY_RE.findall(stripped):
            out.update(_IDENT_RE.findall(body))
        out.update(_TYPEDEF_NAME_RE.findall(stripped))
    return frozenset(out)


def _is_literal(expect: str) -> bool:
    return bool(_NUMBER_RE.match(expect))


# C 字符串字面量的转义表（反斜杠与引号必须先转，否则会把后面的字节解释错）
_C_ESCAPES = {"\\": "\\\\", '"': '\\"'}


def escape_c_string(text: str) -> str:
    """C 字符串字面量内容 → **纯 ASCII** 源码写法（非 ASCII 一律转义）。

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
    * **把非 ASCII 转义成 ASCII 转义序列** → 0 error，编译出的字节与原文逐字节
      相等（本函数）。

    取后者：不动母版、不依赖任何编译器的本地化设置，上网后学生看到的还是同一个
    字（串口按 UTF-8 解就是中文）。转义只换写法，不改字。

    ## ⚠ 为什么是**三位八进制**而不是 `\\xNN`（工单 module-hwcheck/05 的真机判例）

    `\\x` 转义会**贪婪地吃十六进制数字**：`±2g` 的字节序列是 `C2 B1 32 67`，
    写成 `\\xc2\\xb12g` 后编译器把 `\\xb12` 读成**一个**转义（0xB12 越界）——
    ARMCC 报 `#27-D: character value is out of range`，学生看到的字节也就不对了。
    凡是"非 ASCII 字节后面紧跟 `0-9a-f`"的文案都会中招（`±2g` / `°1` / 「3 轴」
    这类读数单位最容易）。

    八进制转义**最多三位数字**，天然自终止：`\\302\\261` 后面跟 `2g` 谁也不会
    连读。仍然只换写法（编译出的字节与原文逐字节相等），只是不再看后续字符的
    脸色。
    """
    out: list[str] = []
    for char in text:
        if char in _C_ESCAPES:
            out.append(_C_ESCAPES[char])
        elif ord(char) < 128:
            out.append(char)
        else:
            # 三位八进制（字节 ≥ 0x80 时 `:03o` 恰好是三位，自终止）
            out.extend(f"\\{byte:03o}" for byte in char.encode("utf-8"))
    return "".join(out)


def c_string(text: str) -> str:
    """带引号的 C 字符串字面量（转义单源——渲染产物里每个字面量都走它）。"""
    return f'"{escape_c_string(text)}"'


def validate_recipes(
    recipes: Mapping[str, Mapping[str, RecipeSection]],
    manifests: Sequence[ModuleManifest],
    interfaces: Mapping[str, Mapping[str, frozenset[str] | set[str]]],
    headers: Mapping[str, frozenset[str] | set[str]] | None = None,
) -> None:
    """引用校验（**本单的核心守卫**）：键必须是库内 slug、必须有该平台条目、
    引用的函数名必须在该模块该平台的头文件接口清单内。任一不满足 → 中文大声失败。

    `interfaces` = **按平台分开**的接口清单：`{平台: {slug: 该模块该平台头文件里的
    名字集合}}`（函数 + 函数式宏 + 对象宏 + extern 全局量，与生成门禁同一份提取：
    `skeleton.extract_header_functions`；由 `interface_names` 逐平台装配）。

    ⚠ **为什么必须按平台分开**（工单 05 修的一处真缺陷）：同一件在两个平台上的
    接口本来就不一样——`ml_mpu6050` 的 stm32 侧有 `MPU6050_Read` / `ax`，mspm0 侧
    有 `DMP_Init` / `DMP_Read_Data`，两边互不相认。早先只传一份清单，于是"用
    mspm0 的清单去查 stm32 的配方段"——平台不对称一出现就误报（实测：mspm0 预览
    400 说 stm32 的 `ax` 找不到）。现在**每段按自己的平台取清单**。

    两条刻意的宽免：

    * **该段拿不到接口集就不判**——`files: []` 的平台条目（实现内嵌母版）在拿不到
      母版头时清单为空（如只用模块库、没配母版库的场景），或调用方这次没给那个
      平台的清单。判不了就不假装判过、也不冤枉好配方（真实库装配点两个平台都给）；
    * **`prereq` 段按"该平台库内任何模块的接口"判，不是只按本件**（工单 05 定：
      前置调用天生是跨模块的——stm32 侧 `ml_mpu6050` 要先调母版的 `I2C_Init()`
      初始化软 I2C 总线，那是 ml_i2c 的接口，本件自己一个字都不声明）。
      判据取"本件 ∪ 该平台库内全部模块 ∪ 母版"的并集：既拦得住拼错的名字，
      又不会把"另一个模块提供的初始化"当成非法。
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
            platform_names = interfaces.get(platform) or {}
            known = set(platform_names.get(slug, frozenset()))
            if not known:
                # 这个 slug 在该平台拿不到任何接口（模块实现内嵌母版 + 调用方没给
                # 母版头 / 这次没给这个平台的清单）——判不了就不判，不冤枉好配方、
                # 也不放过有清单的（真实库装配点两个平台都给，那条路上判据完整）。
                continue
            # 前置调用的判据面：该平台库内**任何**模块 ∪ 母版（跨模块前置调用天生如此）
            library_wide: set[str] = set()
            for names in platform_names.values():
                library_wide |= set(names)
            # include 段的判据面（工单 05）：该平台工程里可能出现的头文件名
            platform_headers = headers.get(platform) if headers is not None else None
            if platform_headers:
                for header in section.include:
                    if header.lower() in platform_headers:
                        continue
                    raise HwCheckError(
                        f"{_where(slug, platform, 'include', section.source)}"
                        f"引用了库内 / 母版里都没有的头文件 {header!r}"
                        "——头名写错会在生成时被 include 解析门拦下（那里也点名），"
                        "但配方是人写的库内数据，写错就该在配方校验这一层当场红"
                    )
            # 这一节自己声明的局部变量（工单 05）：名字进白名单（读数表达式里写
            # `pitch` 是在读自己声明的变量），**类型词仍要过判据**——`folat pitch`
            # 这种手滑不该漏到编译期。
            known |= local_names(section.locals)
            for word in local_type_names(section.locals):
                if word in _C_KEYWORDS or word in known:
                    continue
                raise HwCheckError(
                    f"{_where(slug, platform, 'locals', section.source)}里"
                    f"局部变量声明的类型 {word!r} 既不是 C 关键字、也不在该模块 "
                    f"{platform} 侧的接口清单里（拼错的类型名会在这里被拦下）"
                )
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
            # 前置调用（工单 05 起纳入判据）：只按调用名查，判据面 = 库内任何模块
            # ∪ 母版（跨模块前置调用天生如此，见 docstring）。写在最后：前面几段
            # 的报错更具体，先报它们。
            for expression in section.prereq:
                for name in _calls_in(expression):
                    if name in library_wide:
                        continue
                    raise HwCheckError(
                        f"{_where(slug, platform, 'prereq', section.source)}"
                        f"引用了库内找不到的前置调用 {name!r}（表达式：{expression}）"
                        "——前置调用可以是别的模块 / 母版提供的（如 stm32 侧先调"
                        " I2C_Init() 初始化软 I2C 总线），但它必须真在库内存在"
                    )


def load_recipes(
    module_library_dir: Path | str,
    manifests: Sequence[ModuleManifest],
    interfaces: Mapping[str, Mapping[str, frozenset[str] | set[str]]] | None = None,
    *,
    recipe_path: Path | str | None = None,
    headers: Mapping[str, frozenset[str] | set[str]] | None = None,
) -> dict[str, RecipeCatalog]:
    """读库内配方文件 → 校验 → `{slug: RecipeCatalog}`。

    三种结局（与"缺件 / 坏件"的区分一致，见模块头）：

    * 文件不在 → 空字典（老库照常生成，全走通用降级）；
    * 文件在但 JSON 非法 / 形状不对 / 引用不存在的接口 → `HwCheckError` 中文；
    * 正常 → 逐条 RecipeSection，按 slug 归成目录。

    `interfaces` 缺省 = 只判形状不查函数名（文档 / 探针脚本够用）；检测页与
    生成侧**必须**传（那是本单的守卫）。形状 = `{平台: {slug: 名字集合}}`
    （`interface_names` 逐平台装配后自己套上平台键）——**按平台分开**是硬要求，
    见 `validate_recipes` 的说明：两个平台的接口互不相认，混在一起会误报。

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
        validate_recipes(parsed, manifests, interfaces, headers)
    return {
        slug: RecipeCatalog(slug=slug, sections=sections)
        for slug, sections in parsed.items()
    }


def load_library_recipes(
    module_library_dir: Path | str,
    masters_dir: Path | str,
    manifests: Sequence[ModuleManifest],
    *,
    recipe_path: Path | str | None = None,
) -> dict[str, RecipeCatalog]:
    """库内配方装载（检测页装配的装载入口）→ `{slug: RecipeCatalog}`。

    接口清单 = `interface_names`（模块头 ∪ 母版头）——与生成门禁同一套提取，所以
    "配方过了校验"就等于"生成门禁认这些调用"（**提取**同一套，不是"生成侧也读
    配方"：配方只有检测页消费）。母版头从母版目录现读（stm32 的
    led / oled / delay 是 `files: []` 的空条目，实现内嵌母版，能调的函数全在
    母版头里）。

    母版目录**不存在**（还没导入母版）时按"没有母版头"处理：配方校验的
    `interface_names` 对空清单是宽免的（判不了就不判），页面照常可用——检测页
    的"本平台能不能测"另有平台条目判据兜底（板侧视图的 missing）；**配方文件
    本身坏了仍然是 400**（那条判据不降级，否则坏配方会悄悄溜过去）。

    `recipe_path` 缺省 = 按库根推（`recipe_library_path`）；显式给 = 读另一个
    文件（测试注入坏配方时用，不改真库那一份——并行用例会互相读到半截）。

    **接口清单按平台分开装配**（工单 05 修的一处真缺陷）：配方文件是**全平台
    一份**，校验时每段要按**它自己的平台**取接口清单——只给当前平台那一份的话，
    平台不对称一出现就误报（实测：拿 mspm0 的清单去查 stm32 的 `ax`，mspm0 预览
    直接 400）。所以这里把**所有已注册平台**的清单都装出来，与用户当前选哪个
    平台无关：配方里任何一段写错，任何一次预览都会当场红。

    **母版工程树不可用的平台跳过校验**（"判不了就不判"，工单 04 定、05 校准）：
    清单 = 模块头 ∪ 母版头，而 stm32 侧有一批函数**只住在母版里**（`OLED_Init` /
    `oled_show_text` 在 ml_oled，模块目录里一个声明都没有）。用户还没导入母版
    （或母版目录是空的）时清单天然不全——照判会把好配方判成拼错（本单实测：
    修好"大写函数名没过判据"这个漏洞后，空母版下 `OLED_Init` 立刻误报）。所以
    只有**母版工程树真的在**（目录非空）才判那个平台；真实库的完整判据另有
    地位断言（`test_real_library_recipes_reference_only_real_interfaces`）兜底。
    """
    library = Path(module_library_dir)
    interfaces: dict[str, dict[str, frozenset[str]]] = {}
    headers: dict[str, frozenset[str]] = {}
    for name in sorted(KNOWN_PLATFORMS):
        master_dir = master_project_dir(Path(masters_dir), name)
        if not master_dir.is_dir() or next(iter(master_dir.iterdir()), None) is None:
            continue
        master_headers = [
            (path.relative_to(master_dir).as_posix(),
             path.read_text(encoding="utf-8", errors="replace"))
            for path in iter_project_files(master_dir, pattern="*.h")
        ]
        interfaces[name] = interface_names(manifests, library, name, master_headers)
        # include 段的判据面（工单 05）：库内每个模块该平台条目声明的 .h 基名
        # ∪ 母版树的 .h 基名——与生成门禁的 include 解析门同口径。
        headers[name] = platform_header_names(manifests, name, master_headers)
    return load_recipes(
        library, manifests, interfaces,
        recipe_path=recipe_path,
        headers=headers,
    )


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

    再并入 **`extern` 全局量名**（`extern int16_t ax, ay, az;`，`_extern_names`，
    工单 05）：模块的公开**数据**接口同样是接口——stm32 的 `ml_mpu6050` 把六轴
    原始值放在 extern 全局量里，配额不认它们，读数就写不出来。

    再并入 **enum 常量名与 typedef 类型名**（工单 09 实测的真缺口）：
    `typedef enum { ADC_Channel_0, … } ADCINx_enum;` 里的常量是**真实存在的
    接口名**，而且是"通道 / 模式"这类参数最自然的写法——生成门禁的提取只收
    函数声明与 `#define`，枚举体里的名字一个都不在里面。不并进来的后果不是
    "少一个名字"，而是**配方被逼着绕道**：stm32 的 adc 读数只能写成"整型变量 +
    强转"，代价是 4 个 `#188-D: enumerated type mixed with another type`
    （检测程序的验收线是 0 error / **0 warning**）；直接写 `adc_get(ADC_1,
    ADC_Channel_0)` 反而过不了校验。方向与 `_define_names` / `_extern_names`
    一致：**宁可多认，不可冤枉头文件里真实写过的名字**。

    四个补充提取器收在一处（`_header_names`）：母版头与模块头两条路径共用同一句，
    加第五个提取器只改那一处（原来两个调用点各抄三行，改一处忘另一处就会让
    "母版头认、模块头不认"这种半生效的怪状态——本单评审抓到）。
    """
    from .skeleton import extract_header_functions, format_interface_blocks

    master_names = frozenset(
        extract_header_functions(
            format_interface_blocks(
                [("母版", rel, text) for rel, text in master_headers]
            )
        )
    ) | _header_names(master_headers)
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
        plain = [(rel, text) for _slug, rel, text in headers]
        out[manifest.slug] = (
            frozenset(extract_header_functions(format_interface_blocks(headers)))
            | master_names
            | _header_names(plain)
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


def sections_payload(
    sections: Sequence[RecipeSection],
    commands: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """逐件专精小节的载荷（页面只渲染，不重推判据）。

    字段 = 配方各段的可见面 + `tag`（专精件与未专精件外观可区分的判据，前端只
    上样式）——`include` / `locals` / `prereq` / `platform` 这一版页面用不上，但
    它们是配方契约的一部分（工单 05 的头文件 / 局部变量与探头、06 的命令表都要
    读同一份载荷），留着不算投机抽象：前端不读不等于载荷可以缺，缺了下一个工单
    就得改端点。

    `commands`（工单 hwcheck-specialize/01）＝ **分配后的命令字符**（`slug → 字符`，
    由 `hwcheck_console.build_console_table` 产出）。配方里的 `console.command` 只是
    "这一件想用哪个字符"，首选被别的器件占了之后实际敲的是候选里的某一个——页面
    必须显示**实际那一个**，否则会出现"两件都写着敲 l"的错位。不给（旧调用方 /
    纯载荷测试）= 照旧读配方首选；给空映射与不给同义（没分配结果可覆盖）。
    """
    assigned = commands or {}
    return [
        {
            "slug": section.slug,
            "platform": section.platform,
            "tag": SECTION_TAG,
            "include": list(section.include),
            "locals": list(section.locals),
            "prereq": list(section.prereq),
            "init": list(section.init),
            "init_expect": section.init_expect,
            "probe": (
                None if section.probe is None
                else {"calls": list(section.probe.calls),
                      "expect": section.probe.expect}
            ),
            "has_probe": bool(section.probe and section.probe.expect),
            "read": [
                {"expression": item.expression, "unit": item.unit}
                for item in section.read
            ],
            "console": (
                None if section.console is None
                else {"command": assigned.get(section.slug, section.console.command),
                      "description": section.console.description}
            ),
            "note": list(section.note),
        }
        for section in sections
    ]


def render_recipe_section(
    section: RecipeSection, report: dict[str, Any] | None = None
) -> list[str]:
    """一件器件的检测小节 → 缩进好的 C 语句（纯函数，可逐字断言）。

    形态（确定性）：注释块（哪一件 / 平台说明 / 专精声明）→ 小节头
    `hwcheck_section` → 局部变量声明 → 前置调用 → 初始化 → 通信探头 → 读数回显
    → 判定记账（`hwcheck_verdict*`，结尾汇总数得出来"真测了几件"）。

    **两级判定**（spec 判据三层里的第②层；判定都在板上算）：

    * 判据 = 配方写了 `init_expect`（初始化返回值约定）或 `probe.expect`
      （通信探头期望值）：**判定在板上算**（比较式落进渲染出的 C），探
      不到就打 FAIL 并**直接 return**——不通就不再打一堆无意义读数。
    * 判不了（`void` 初始化没有返回值可判 / 纯输出件没有可读寄存器，如
      led / oled）= 如实打 `hwcheck_verdict_probe_none` + "只看现象"，
      **不算通过**。`probe.calls` 允许只做动作、不带期望值（如让 OLED
      显示一行"我活着"作为肉眼现象），此时仍不打判定。

    ⚠ **字面量一律经 `c_string` 转义**（非 ASCII → 三位八进制转义）：ARMCC 5.06 按
    本地代码页解析源文件，原样中文字面量会让整份 main.c 编不过（真机判例见
    `escape_c_string` 的 docstring）。注释里保留中文——那是给人读的，不影响解析。

    `report` 非空时被填进这一节的观测：`slug` / `probe`（有没有带期望值的探头）/
    `trouble`（排查指引）。渲染本身不打印、不读盘。

    ⚠ **不写 `verdict`**（评审整改，04 的坑）：判定结果要到板上才算得出来，渲染期
    写了只会是恒定值，汇总侧照它分支就是一条永不触发的死路。
    """
    probe = section.probe
    judged_probe = probe is not None and bool(probe.expect)
    judged_init = bool(section.init_expect)
    out: list[str] = [
        f"    /* ---- {SECTION_TAG} {section.slug}：按库内配方测这一件 ---- */",
    ]
    for note in section.note:
        out.append(f"    /* 平台说明：{note} */")
    out.append(
        "    /* 专精件：这一节真的会驱动它 / 读它（库内配方给的动作）。"
        "未专精件走通用降级，出的是另一套小节（工单 07，不带 [专精] 标记）。 */"
    )
    out.append(f"    hwcheck_section({c_string(f'{SECTION_TAG} {section.slug}')});")

    if judged_init or judged_probe:
        out.append("    int r;")
    # 这一节自己声明的局部变量（工单 05）：排在所有动作之前——`probe` 里那句
    # `DMP_Read_Data(&pitch, &roll, &yaw)` 就是靠它们把角度搬出来的。
    for declaration in section.locals:
        out.append(f"    {declaration};")
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
