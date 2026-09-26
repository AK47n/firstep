# -*- coding: utf-8 -*-
"""硬件检测的**通用降级**（工单 module-hwcheck/07）：未专精件也能上板一测。

## 这一层解决什么

spec 的 v1 专精范围只有十件「模块 × 平台」，库内有 168 格没有配方。没有这一层，
选了它们就"什么都没有"——学生手上那件东西到底通不通，仍然只能猜。

通用降级 = **初始化 +（I2C 类件）总线地址扫描**，两条判据都取自库内**已声明的
事实**（该模块头文件里的函数声明、manifest 的引脚角色与宏），不引入"这件器件该
怎么读"这类新知识：

* **初始化**：从该模块**自己头文件里的函数声明**找（`plan_init`）——判据三级：
  精确 `<slug>_init` → 唯一一个能无参调的 `*_init` → **认不出就不调**。
  为什么必须"声明为无参"才算：通用降级不知道参数该给什么
  （`servo_init(servo_id, channel)` / `pca9685_init(freq_hz)` / `motor_init(id)`
  全都要参数），编一个参数出来就是猜——编不过还好，编过了才是灾难（板子上
  按一个凭空来的参数跑起来，学生以为"测过了"）。实测：168 个未专精格里
  **140 格**拿得到无参初始化（131 精确命中 + 9 唯一兜底），28 格认不出
  （`.scratch/module-hwcheck/probe-07-init-callable.txt`）。
* **总线扫描**：只在该件**声明了 `i2c_scl` / `i2c_sda` 引脚角色**（manifest 的
  事实）**且两个角色都给了端口 / 引脚宏**时才渲染（`scan_for_pins`）。扫的是
  **这一件自己那条总线**——宏是 pin_config.h 的宏，模块自己的驱动读的也是这一对
  （拿母版 ml_i2c 那条 PA11/PA12 去扫 PA6/PA7 上的器件，只会得到一句假的"无应答"）。
  为什么"有宏"这一条不能省（票面只写了"声明了 I2C 角色"）：模块自己的位操作原语
  是 **static**（`sht20_stm32.h` 只暴露 `sht20_init` / `sht20_read`，`sht20_iic_*`
  在 .c 里），渲染器手里**只有那对宏**能驱动总线——没宏就驱动不了，于是如实不扫、
  并把原因写进检测页与产物（`GenericSection.scan_note`），不假装扫过。
  ⚠ 扫描标签印的是 manifest 声明的**默认脚**（没人改绑时的真脚）；总线本身走宏
  （`pin_config.h` 的值）驱动，所以即便将来改绑，扫的仍是那条总线的真脚——只有
  **印出来的脚名**会落后于绑定结果（检测页目前不支持改绑，工单 03 记的账；将来
  支持了，这个标签要跟着绑定走）。

## 绝不猜读函数（spec 硬约定）

通用小节**不产生任何读调用**：不读身份寄存器、不读传感器值——"猜出来的垃圾值
比不测更坏"。所以这一节在板上只做两件事：调一次初始化、ping 一遍地址；扫不出
应答就如实说"无应答，先查供电 / 上拉 / 线序"，绝不编一个读数出来。

`tests/test_hwcheck_generic.py` 有一条结构守卫钉住这条：通用小节的调用集里，
属于该模块接口的**只有初始化**那一个。

## 「未专精」标注（措辞单源，但**按这一趟真做了什么分三种**）

标注只有一处出处：本模块的 `GENERIC_LABEL*` 常量。它同时进产物小节的细节行与
检测页的点名（前端一个字都不另写）——两处各写一句就会漂成两种说法，而学生正是
靠这句话判断"哪些结论可信、哪些只是走了个过场"（spec 用户故事 10）。

标什么**取决于这一趟真做了什么**（票面「不假装测过」的底线）：

| 这一趟 | 标注 |
|---|---|
| 调了无参初始化（± 扫描） | `GENERIC_LABEL`「未专精：只验总线和初始化」 |
| 没调初始化，只扫了总线 | `GENERIC_LABEL_SCAN_ONLY` |
| 既没初始化也没扫描（28 格） | `GENERIC_LABEL_IDLE`——**绝不印"只验总线和初始化"** |

第三行是本单自查抓到的一条假话：那 28 格的初始化要参数（或没有模块头），通用
降级**一个动作都做不了**，此时再印「只验总线和初始化」就是"拿没做的事当好结果"。

专精件带 `SECTION_TAG`（`[专精]`），通用件**不带**——外观可区分是这一单的验收线
之一。

## 与配方层的关系

配方（`hwcheck_recipe.py`）是"这一件怎么测"的**库内数据**；本模块是"没有数据
时怎么诚实地走个过场"。两者产出同一种小节的**渲染位置**（`hwcheck.render_main_c`
的顺序、汇总、按需渲染都吃），但判据面完全不同，所以是两个模块而不是一个
（照 `hwcheck_console.py` 的先例分工）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .clex import strip_comments
from .hwcheck_recipe import c_string
from .manifest import ModuleManifest, PinDeclaration

__all__ = [
    "GENERIC_LABEL",
    "GENERIC_LABEL_IDLE",
    "GENERIC_LABEL_SCAN_ONLY",
    "SCAN_ADDRESS_FIRST",
    "SCAN_ADDRESS_LAST",
    "BusScan",
    "GenericSection",
    "InitPlan",
    "declare_functions",
    "generic_message",
    "plan_generic_section",
    "plan_init",
    "read_module_headers",
    "render_generic_runtime",
    "render_generic_section",
    "resolve_generic_sections",
    "scan_for_pins",
]

# 「未专精」标注（**措辞单源**：产物小节 + 检测页点名共用，前端一个字不另写）。
# 为什么是这句话：它要一眼回答"这一趟对这件做了什么"——只验总线和初始化，
# 没验数据。说成"检测中"或"部分支持"都会让人以为读到的数有人负责（spec
# 用户故事 10：哪些结论可信、哪些只是走了个过场）。
#
# ⚠ 这一句只在**真的做了初始化**时成立（见下面两条）；三选一的判据是
# `GenericSection.label`——标错就是"拿没做的事当好结果"，本单自查抓到过。
GENERIC_LABEL = "未专精：只验总线和初始化"
# 认不出无参初始化、但**扫了总线**（如 `pca9685_init(freq_hz)` 要参数而 I2C 角色齐全）
GENERIC_LABEL_SCAN_ONLY = "未专精：没有可执行的初始化，只扫了总线"
# 既没初始化也没扫描：168 格里 28 格（初始化要参数 / 该平台没有模块头）。
# 这时候**一个动作都没做**，绝不能印"只验总线和初始化"。
GENERIC_LABEL_IDLE = "未专精：这一趟没有可执行的动作（认不出可无参调用的初始化）"

# I2C 引脚角色（manifest `pins[].type`，词表单源 = manifest.PIN_ROLE_TYPES）。
_I2C_SCL = "i2c_scl"
_I2C_SDA = "i2c_sda"

# 总线扫描的地址区间（7 位地址的合法从机地址段；0x00–0x07 与 0x78–0x7F 是保留段，
# 扫它们只会得到噪声）。这一段是 I2C 规范的事实，不是猜出来的。
SCAN_ADDRESS_FIRST = 0x08
SCAN_ADDRESS_LAST = 0x77

# 函数**声明**（不是定义）的机械判据：`名字 ( 形参表 ) ;`
#
# 两条刻意的取舍：
#   * 形参表排掉 `;` `{` `)`——函数定义（后面跟 `{`）、调用、函数指针声明
#     （`void (*cb)(void);`）因此都匹配不上；跨行声明由 `[^;{)]*` 自己吞掉
#     （它含换行），形参文本再做空白归一。
#   * 只在**剥掉注释与字面量**的文本上匹配（`clex.strip_comments`）：注释里
#     写的 `/* foo_init(void); */` 是文档不是接口，把它当候选就是拿注释当判据。
_DECL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(([^;{)]*)\)\s*;")

# 「能无参调」的形参写法：C 里只有这两种（`void` 与空表）。
_NO_PARAM_FORMS = frozenset({"", "void"})


def declare_functions(
    headers: Sequence[tuple[str, str]],
) -> dict[str, frozenset[str]]:
    """头文件集 → `{函数名: {形参表写法}}`（声明，不含定义）。

    `headers` = `[(相对路径, 文本)]`（与 `hwcheck_recipe.interface_names` 吃的
    形状一致，方便调用方共用同一份读盘结果）。同一名字在多份头文件里出现多次
    时形参表取并集——判"能不能无参调"时要求**全部**写法都无参（一份声明要参数、
    一份不要，那不是"能无参调"，是接口不一致）。
    """
    out: dict[str, frozenset[str]] = {}
    for _rel, text in headers:
        for match in _DECL_RE.finditer(strip_comments(text)):
            name = match.group(1)
            params = re.sub(r"\s+", " ", match.group(2)).strip()
            out[name] = out.get(name, frozenset()) | {params}
    return out


def _callable_without_arguments(
    name: str, declarations: dict[str, frozenset[str]]
) -> bool:
    """这个名字是不是**声明为无参**（`name(void)` / `name()`）——通用降级唯一敢调的形态。"""
    forms = declarations.get(name)
    return bool(forms) and forms <= _NO_PARAM_FORMS


@dataclass(frozen=True)
class InitPlan:
    """通用降级该调的初始化：`name` 空 = 认不出，`reason` 说清为什么。

    为什么要把"为什么认不出"做成数据而不是只说一句"没有初始化"：这一节最终
    要在板子上**什么都不做**，而学生看到的现象与"初始化过了"一模一样。理由进
    产物注释与检测页，学生才知道该去哪儿补（写配方 / 改库）。
    """

    name: str = ""
    reason: str = ""


def plan_init(slug: str, declarations: dict[str, frozenset[str]]) -> InitPlan:
    """通用降级该调的初始化函数（认不出 = 空名 + 中文理由，**绝不猜**）。

    三级判据（顺序即优先级）：

    1. **精确** `"<slug>_init"` 且声明为无参——库内命名约定的主形态
       （实测：168 个未专精格里 131 格命中）；
    2. **唯一**一个能无参调的 `*_init`——名字不带 slug 前缀的那几件
       （`ir_tx_init` / `IMU_Init` / `xpt2046_init` / `gp2y1014_init`，实测 9 格）；
    3. 两个都能无参调、又没有精确命中 → **空名**。真实库里目前**没有**这一格
       （`pid` / `motor` 都有精确命中的 `pid_init` / `motor_init`，另一路
       `gray_init` / `encoder_init` 因此不进第二级）——但判据必须留着：库一演进
       （新模块带两个 init）它就会用上，宁可不测也不猜哪一个。
       初始化要参数（`servo_init(servo_id, channel)` / `pca9685_init(freq_hz)`）
       或压根没有头文件（`files: []`，实现内嵌母版）同样落这一级：**空名** +
       中文理由，这一节如实说清，不在板上做动作。

    第 3 条是这一层的性格所在：宁可少测一样，也不编一个调用出来。认错初始化
    比不初始化更坏——学生会拿"初始化跑过了"当"这件是好的"。
    """
    exact = f"{slug}_init"
    if _callable_without_arguments(exact, declarations):
        return InitPlan(name=exact)
    candidates = sorted(
        name for name in declarations
        if name.lower().endswith("_init")
        and _callable_without_arguments(name, declarations)
    )
    if len(candidates) == 1:
        return InitPlan(name=candidates[0])
    if candidates:
        return InitPlan(reason=(
            f"有多个可无参初始化（{' / '.join(candidates)}），认不出该调哪个"
        ))
    declared = sorted(
        name for name in declarations if name.lower().endswith("_init")
    )
    if declared:
        forms = sorted(
            form for name in declared for form in declarations[name]
        )
        return InitPlan(reason=(
            f"初始化需要参数：{declared[0]}({forms[0]})（通用降级不猜）"
        ))
    return InitPlan(reason=(
        f"本件没有可无参调用的初始化（模块头里没有 {slug}_init 这类声明）"
    ))


@dataclass(frozen=True)
class BusScan:
    """这一件**自己那条** I2C 总线（宏名，不是引脚字面量）。

    为什么是宏而不是 `PA6`：宏的值住在生成工程的 `pin_config.h` 里，用户改绑
    引脚只改那一处——渲染器写死 `GPIO_A/Pin_6` 就会与绑定结果脱钩（ADR 0010
    板级引脚配置）。`macros` 的顺序由 manifest 声明固定为 `(端口, 引脚)`
    （`PinDeclaration.macros` 的既有约定，ml_i2c 与各软 I2C 件同款）。

    地址区间**不在这里**：它是 I2C 规范的事实，单源 = `SCAN_ADDRESS_FIRST/LAST`
    （`render_generic_runtime` 直接拿它们渲 C）——放一份到数据类里就是第二个
    判据源，而且没人读（本单评审抓到过这两个死字段）。
    """

    scl_port: str
    scl_pin: str
    sda_port: str
    sda_pin: str


def scan_for_pins(pins: Sequence[PinDeclaration]) -> BusScan | None:
    """引脚角色声明 → 这一件能不能扫、拿什么扫（不能 = None）。

    三条同时成立才算 I2C 类（**判据零新增知识**，全是 manifest 已声明的事实）：

    1. 声明了 `i2c_scl` 角色；
    2. 声明了 `i2c_sda` 角色（只有一半开不出总线）；
    3. 两个角色都给了**两个**宏（端口 + 引脚）——mspm0 侧走 SysConfig 实例、
       manifest 里 `macros` 为空（实测 16 格可扫的全是 stm32），渲染器没有能
       驱动那条总线的名字：**不扫，也不去猜实例名**。
    """
    scl = next((pin for pin in pins if pin.type == _I2C_SCL), None)
    sda = next((pin for pin in pins if pin.type == _I2C_SDA), None)
    if scl is None or sda is None:
        return None
    if len(scl.macros) != 2 or len(sda.macros) != 2:
        return None
    return BusScan(
        scl_port=scl.macros[0], scl_pin=scl.macros[1],
        sda_port=sda.macros[0], sda_pin=sda.macros[1],
    )


@dataclass(frozen=True)
class GenericSection:
    """一件未专精器件的通用小节（规划结果，纯数据）。

    字段全部来自**已声明的事实**：`init` 来自该模块自己的头文件声明，`scan` /
    `scan_label` / `scan_note` 来自 manifest 的引脚角色，`headers` 来自 manifest
    的平台条目文件清单。没有一项是推出来的。

    `init` 直接持 `plan_init` 的结果（`InitPlan`：名字 + 认不出时的理由）而不是
    拆成两个平行字段：那两个字段是一体的两半，拆开就会出现"有名字没理由 / 有理由
    没名字"的半截状态（本单评审抓到的 Data Clump）。

    `headers` 为什么要带：检测程序要调 `sht20_init()`，就得 include 它的头——
    框架那套固定 include 只覆盖通道与心跳（工单 05 的真机判例：不 include 就是
    隐式声明，ARMCC 报一串 `#223-D`）。
    """

    slug: str
    platform: str
    init: InitPlan = InitPlan()
    headers: tuple[str, ...] = ()
    scan: BusScan | None = None
    scan_label: str = ""
    # 为什么**没**扫（声明了 I2C 角色却驱动不了 / 只声明了一半）：进检测页与产物，
    # 票面只写了"声明了 I2C 角色就扫"，实务上还差"能不能驱动"这一步——不说清就
    # 成了静默收窄（本单评审抓到的第一条）。
    scan_note: str = ""

    @property
    def label(self) -> str:
        """「未专精」标注——**按这一趟真做了什么**三选一（见模块头那张表）。"""
        if self.init.name:
            return GENERIC_LABEL
        if self.scan is not None:
            return GENERIC_LABEL_SCAN_ONLY
        return GENERIC_LABEL_IDLE

    @property
    def plan_text(self) -> str:
        """这一趟对它做什么（检测页那一句 + 产物注释，同一句）。"""
        parts: list[str] = []
        if self.init.name:
            parts.append(
                f"初始化 {self.init.name}()（无参调用；本件未专精，"
                "仅确认初始化不报错）"
            )
        else:
            parts.append(f"没有可执行的初始化：{self.init.reason}")
        if self.scan is not None:
            parts.append(
                f"总线地址扫描（{self.scan_label}，只 ping 地址、不读寄存器）"
            )
        elif self.scan_note:
            parts.append(f"不做总线扫描：{self.scan_note}")
        return " + ".join(parts)


def plan_generic_section(
    platform: str,
    manifest: ModuleManifest,
    headers: Sequence[tuple[str, str]],
) -> GenericSection:
    """一格未专精件 → 通用小节（纯函数：吃 manifest 与已读的头文本）。

    `headers` = 该模块**在 `platform` 上自己那份**头文件（`[(相对路径, 文本)]`）：
    调用方按 manifest 的平台条目读盘（读盘不在本函数里，故可在内存里直测）。
    """
    entry = manifest.platforms.get(platform)
    declarations = declare_functions(headers)
    scan = scan_for_pins(entry.pins) if entry is not None else None
    return GenericSection(
        slug=manifest.slug,
        platform=platform,
        init=plan_init(manifest.slug, declarations),
        headers=tuple(
            Path(rel).name for rel in (entry.files if entry is not None else ())
            if rel.lower().endswith(".h")
        ),
        scan=scan,
        scan_label=_scan_label(entry.pins) if scan is not None else "",
        scan_note=(
            _scan_note(entry.pins) if scan is None and entry is not None else ""
        ),
    )


# 声明了 I2C 角色却驱动不了时，为什么（进检测页与产物，别让"没扫"这件事没说法）
_SCAN_NO_MACROS = (
    "这一件声明了 I2C 引脚角色，但本平台的引脚由 SysConfig 实例给出"
    "（manifest 里没有 pin_config 宏），通用降级手里没有能驱动这条总线的名字"
    "——不猜实例名，也就不扫"
)
_SCAN_ONE_ROLE = (
    "这一件只声明了 I2C 的一半（只有 SCL 或只有 SDA），开不出一条完整的总线"
)


def _scan_note(pins: Sequence[PinDeclaration]) -> str:
    """没扫时的理由（没有 I2C 角色 = 空串：那不是"该扫没扫"，是本来就不适用）。"""
    roles = {pin.type for pin in pins}
    if not roles & {_I2C_SCL, _I2C_SDA}:
        return ""
    if not ({_I2C_SCL, _I2C_SDA} <= roles):
        return _SCAN_ONE_ROLE
    return _SCAN_NO_MACROS


def _scan_label(pins: Sequence[PinDeclaration]) -> str:
    """扫描那一行的人读标签：`SHT20_SCL PA6 / SHT20_SDA PA7`。

    只印 manifest 声明的**默认脚**（页面的接线表也是这一对）——它让串口上那行
    "总线扫描（…）" 自解释：学生不必回电脑上翻接线表就知道扫的是哪两个脚。
    """
    parts = [
        f"{pin.id} {pin.default}"
        for pin in pins if pin.type in (_I2C_SCL, _I2C_SDA)
    ]
    return " / ".join(parts)


def generic_message(section: GenericSection) -> str:
    """检测页的未专精点名（`GENERIC_LABEL` 原话 + 这一趟做什么）。

    为什么不静默省略：悄悄不出现在检测计划里，学生会以为"选了 = 测了"
    （spec「不假装测过」）；而说清"只验了总线和初始化"之后，他才知道哪些结论
    可信（spec 用户故事 10）。
    """
    return f"{section.slug}：{GENERIC_LABEL}——这一趟对它做的事：{section.plan_text}。"


def read_module_headers(
    module_library_dir: Path | str, manifest: ModuleManifest, platform: str
) -> tuple[tuple[str, str], ...]:
    """读该模块在该平台**自己那份**头文件（`[(相对路径, 文本)]`）——判据的原料。

    盘侧动作只在这一处（`plan_generic_section` 本身是纯的，可内存直测）。读不出来
    （文件不在）就跳过那一个：manifest 与盘不一致由库的结构测试兜底，检测页不必
    因此 500。
    """
    entry = manifest.platforms.get(platform)
    if entry is None:
        return ()
    root = Path(module_library_dir) / manifest.slug
    out: list[tuple[str, str]] = []
    for rel in entry.files:
        if not rel.lower().endswith(".h"):
            continue
        path = root / rel
        if path.is_file():
            out.append((rel, path.read_text(encoding="utf-8", errors="replace")))
    return tuple(out)


def resolve_generic_sections(
    platform: str,
    devices: Sequence[str],
    specialized: Sequence[str],
    manifests: Sequence[ModuleManifest],
    module_library_dir: Path | str,
) -> tuple[GenericSection, ...]:
    """选中器件 → 通用降级小节（**票面第一条验收**：不报错、不拒绝）。

    三种器件各有下场，一件都不许静默掉队：

    * **专精件**（`specialized`，= 已有该平台配方的 slug）→ 走配方，不出通用小节
      ——同一件两条小节会渲出两个同名 C 函数，编不过；
    * **通用件**（有该平台条目、没配方）→ 出通用小节（本函数）；
    * **没该平台条目的件** → 不在这里（检测页的 `wiring.missing` 那条路点名
      "该模块无本平台版本，无法检测"）——两处都说一遍反而是两个口径。

    顺序与专精小节**同一函数**（`readme.sort_verification_order`，bring-up 件
    前置）：检测程序里的次序与工程 README 那张清单不一致，学生会照着一个做、
    被另一个打脸。

    `devices` 由调用方给（`hwcheck.hwcheck_devices` 已保序去重）；本函数按 slug
    建索引再取值，重复项自然只出一条。
    """
    from .readme import sort_verification_order

    specialized_set = set(specialized)
    by_slug = {manifest.slug: manifest for manifest in manifests}
    planned: dict[str, GenericSection] = {}
    for slug in devices:
        if slug in specialized_set or slug in planned:
            continue
        manifest = by_slug.get(slug)
        if manifest is None or manifest.platforms.get(platform) is None:
            continue
        headers = read_module_headers(module_library_dir, manifest, platform)
        planned[slug] = plan_generic_section(platform, manifest, headers)
    if not planned:
        return ()
    order = {
        manifest.slug: index
        for index, manifest in enumerate(
            sort_verification_order(
                [by_slug[slug] for slug in planned if slug in by_slug]
            )
        )
    }
    return tuple(
        sorted(
            planned.values(),
            key=lambda section: (order.get(section.slug, len(order)), section.slug),
        )
    )


def render_generic_runtime(sections: Sequence[GenericSection]) -> list[str]:
    """通用降级的**共用运行时**（缩进好的文件作用域语句）。

    **按需渲染**（04/05 编译矩阵纪律）：只有真的有扫描件时才渲染这两个助手
    ——声明了没人调的函数，ARMCC 报 `#177-D`、tiarmclang 报 `-Wunused-function`，
    而验收线是 0 error / 0 warning。

    两个助手的形状：

    * `hwcheck_i2c_ping` —— 发一个起始位 + 地址字节，读第 9 拍的应答。
      **只 ping 地址，一个寄存器都不读**（这是"不猜读函数"的结构证据）。
    * `hwcheck_i2c_scan` —— 扫 `SCAN_ADDRESS_FIRST..SCAN_ADDRESS_LAST`，
      打「应答：0xNN」清单；一个都没有时打「无应答」+ 排查话术
      （供电 / 上拉 / 线序——I2C 不通的三个最常见原因）。

    ⚠ **十六进制助手（`hwcheck_report_hex`）不在这里印**（工单 04 编译矩阵抓到的
    真缺陷）：自建件的「只回显」那一档也要用它，两处各印一份时产物里就出现两个
    同名定义（`error #247: function "hwcheck_report_hex" has already been
    defined`）——两批小节单跑都绿，同趟才炸。现在**唯一产地 = `hwcheck._report_function`**
    （按需渲染的判据在 `render_main_c`：自建件读寄存器 **或** 这一批真有扫描件
    就要），本函数只管"扫"这件事本身。

    引脚由**宏名**参数化（manifest 声明的那两个），不是写死的 `GPIO_A/Pin_6`：
    宏的值住在生成工程的 `pin_config.h`，用户改绑引脚只改那一处（ADR 0010）。
    """
    if not any(section.scan is not None for section in sections):
        return []
    first, last = SCAN_ADDRESS_FIRST, SCAN_ADDRESS_LAST
    return [
        "/* ---- 通用降级运行时（未专精件）----",
        " * 只 ping 地址，不读任何寄存器：通用降级**不猜读函数**（猜出来的垃圾值",
        " * 比不测更坏）。引脚走 manifest 声明的宏（值在 pin_config.h）。 */",
        "/** 发一个起始位 + 地址字节，读第 9 拍的应答；1 = 这一地址有器件应答。 */",
        "static int hwcheck_i2c_ping(GPIOn_enum scl_port, Pinx_enum scl_pin,",
        "                            GPIOn_enum sda_port, Pinx_enum sda_pin,",
        "                            int address)",
        "{",
        "    int i;",
        "    int ack;",
        "",
        "    gpio_init(scl_port, scl_pin, OUT_OD);",
        "    gpio_init(sda_port, sda_pin, OUT_OD);",
        "    gpio_set(sda_port, sda_pin, 1);",
        "    gpio_set(scl_port, scl_pin, 1);",
        "    /* 起始位：SCL 高电平期间 SDA 由高变低 */",
        "    gpio_set(sda_port, sda_pin, 0);",
        "    gpio_set(scl_port, scl_pin, 0);",
        "    /* 地址字节（7 位地址 + 写位） */",
        "    for (i = 0; i < 8; i++)",
        "    {",
        "        gpio_set(sda_port, sda_pin, ((address << 1) & (0x80 >> i)) ? 1 : 0);",
        "        gpio_set(scl_port, scl_pin, 1);",
        "        gpio_set(scl_port, scl_pin, 0);",
        "    }",
        "    /* 第 9 拍：放开 SDA 改输入读应答——低电平 = 有器件应答 */",
        "    gpio_set(sda_port, sda_pin, 1);",
        "    gpio_init(sda_port, sda_pin, IU);",
        "    gpio_set(scl_port, scl_pin, 1);",
        "    ack = gpio_get(sda_port, sda_pin);",
        "    gpio_set(scl_port, scl_pin, 0);",
        "    gpio_init(sda_port, sda_pin, OUT_OD);",
        "    /* 停止位：SCL 高电平期间 SDA 由低变高 */",
        "    gpio_set(sda_port, sda_pin, 0);",
        "    gpio_set(scl_port, scl_pin, 1);",
        "    gpio_set(sda_port, sda_pin, 1);",
        "    return ack == 0;",
        "}",
        "",
        "/** 扫一遍这一件声明的那条总线（只 ping 地址）。 */",
        "static void hwcheck_i2c_scan(GPIOn_enum scl_port, Pinx_enum scl_pin,",
        "                             GPIOn_enum sda_port, Pinx_enum sda_pin,",
        "                             const char *pins_text)",
        "{",
        "    int address;",
        "    int found = 0;",
        "",
        "    hwcheck_report(" + c_string("  总线扫描（") + ");",
        "    hwcheck_report(pins_text);",
        "    hwcheck_report(" + c_string("；只 ping 地址，不读寄存器）：") + ");",
        "    hwcheck_newline();",
        f"    for (address = 0x{first:02X}; address <= 0x{last:02X}; address++)",
        "    {",
        "        if (!hwcheck_i2c_ping(scl_port, scl_pin, sda_port, sda_pin, address))",
        "        {",
        "            continue;",
        "        }",
        "        found++;",
        "        hwcheck_report(" + c_string("    应答：0x") + ");",
        "        hwcheck_report_hex(address);",
        "        hwcheck_newline();",
        "    }",
        "    if (found == 0)",
        "    {",
        # ⚠ 这一行**必须短**：行缓冲是 `hwcheck_line[128]` 字节（框架的溢出保护，
        # 超了会截断），而中文在 UTF-8 下一字 3 字节——本单的行为探针第一次跑就
        # 抓到旧文案（「先查供电、上拉（SDA/SCL 各要 4.7k）、线序（有没有接反）」）
        # 超长，末尾被截成半个多字节字符（终端显示 `�`）。短句同样说清了三个
        # 最常见原因，且 `tests/test_hwcheck.py` 有一条"每行文案不许超过缓冲"的
        # 结构守卫钉住这一整类。
        "        hwcheck_report(" + c_string(
            "    无应答：先查供电 / 上拉 / 线序（有没有接反）"
        ) + ");",
        "        hwcheck_newline();",
        "    }",
        "}",
        "",
    ]


def render_generic_section(section: GenericSection) -> list[str]:
    """一件未专精器件的通用小节 → 缩进好的 C 语句（纯函数，可逐字断言）。

    形态（确定性，与专精小节**外观可区分**）：

    * 注释块与细节行带 `section.label`（**不带 `SECTION_TAG`**——专精标记是那一件
      的特权，通用件带上它，"哪些结论可信"就没人分得清了）；
    * 标注**按这一趟真做了什么**三选一（`GenericSection.label`）：调了初始化 /
      只扫了总线 / 什么都没做——第三种绝不印「只验总线和初始化」（本单评审抓到的
      假话）；
    * 初始化：认得出就调（**无参**，不判返回值——没有约定可判），认不出就如实
      把理由打出来（`init.reason`），**不编调用**；
    * 有扫描件时调 `hwcheck_i2c_scan(...)`，参数 = manifest 声明的宏名 + 人读标签；
      声明了 I2C 角色却驱动不了时，把 `scan_note` 打到板上（不静默收窄）；
    * `hwcheck_verdict_probe_none`：**不算通过**（板上没有判定项），汇总里计入
      「未判定」那一档；
    * 一句"数据正不正常这一版不看"教学生别把走过场当验证过。

    ⚠ 字面量一律经 `c_string` 转义（ARMCC 5.06 按本地代码页解析源文件，原样
    中文会把收尾引号吞掉——工单 04 的真机判例）。
    """
    label = section.label
    out: list[str] = [
        f"    /* ---- {label} ---- */",
        "    /* 通用降级：这一件没有专精配方——只做",
        "     * 初始化 +（声明了 I2C 脚才做）总线地址扫描，**不猜读函数**"
        "（猜出来的垃圾值比不测更坏）。 */",
        f"    hwcheck_section({c_string(section.slug)});",
        f"    hwcheck_detail({c_string(label)});",
    ]
    if section.init.name:
        # **真的调**（不是只在报告里提一句）：票面要的是"只做初始化"，
        # 报告行只是让人在串口上看到这件事发生过。
        out.append(
            f"    {section.init.name}();   /* 无参调用；本件未专精，"
            "仅确认初始化不报错 */"
        )
        out.append(
            "    hwcheck_report("
            + c_string(
                f"  初始化：{section.init.name}() 已调用"
                "（本件未专精，不判返回值）"
            )
            + ");"
        )
    else:
        # 一句短标题 + 细节行（理由里有函数签名，可能长）：两者各自都要塞得进
        # `hwcheck_line[128]`（见 render_generic_runtime 的说明与行缓冲守卫）。
        out.append(f"    hwcheck_report({c_string('  这一节没有可执行的初始化')});")
        out.append("    hwcheck_newline();")
        out.append(f"    hwcheck_detail({c_string(section.init.reason)});")
    out.append("    hwcheck_newline();")
    if section.scan is not None:
        scan = section.scan
        out.append(
            "    hwcheck_i2c_scan("
            f"{scan.scl_port}, {scan.scl_pin}, {scan.sda_port}, {scan.sda_pin}, "
            + c_string(section.scan_label) + ");"
        )
    elif section.scan_note:
        out.append(
            "    hwcheck_detail(" + c_string(f"不做总线扫描：{section.scan_note}") + ");"
        )
    out.append(
        "    hwcheck_verdict_probe_none("
        + c_string(f"{section.slug}：{label}——不算通过，只看现象")
        + ");"
    )
    out.append(
        "    hwcheck_detail("
        + c_string("本件没有专精配方：数据正不正常这一版不看，"
                   "请对照检测页清单看现象")
        + ");"
    )
    out.append("")
    return out
