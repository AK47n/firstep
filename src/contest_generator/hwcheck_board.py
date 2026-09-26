"""硬件检测页的板侧投影（工单 module-hwcheck/03）：接线行 / 同脚冲突 / 建议顺序。

**判据一行都不新立**——三块全部是对既有单源的投影，本模块只把它们拼成检测页要的形状：

* **接线行** = `wiring.wiring_rows`（与工程 README「引脚接线表」同一推导
  `readme._pin_row_items`）——页面上那几根线就是工程 README 里那几根，两处各推
  一遍必然漂移：学生照着页面插好线，打开工程 README 却是另一组脚。
* **共享 / 冲突** = `pin_bindings._shared_groups`（同一 I2C 总线 / 同一串口实例 /
  同一 syscfg 器件实例 = 合法共享；同脚分属不同外设 = 物理冲突）。
* **建议顺序** = `readme.sort_verification_order` + `readme.BRING_UP_SLUGS`
  （bring-up 前置的稳定分区，与工程 README「验证顺序清单」同一排序）。
* **引脚消解**（工单 hwcheck-pin-conflict-exit/01）= `hwcheck_pin_plan`：检测页
  没有引脚配置入口，所以它**在生成前自己把默认脚撞脚解开**——与赛题页「自动配置」
  同一个求解器（`auto_assign_bindings(resolve_default_conflicts=True)`）、同一个
  落盘冲突判据（`syscfg_prune.syscfg_pin_conflict_report`），并把「动了哪几根线」
  如实带出。接线表按**消解后**的脚渲染（学生照表接线），工程 README 同源。

板上共享注记（如地猛星 PA0/PA1「板载 LED 共用（I2C_0 SDA，通信期间微闪）」）
取自板定义 `BoardPin.notes`——那是**板的事实**，不是本模块的判断，页面照抄。

为什么值得单独立一个域模块：这是本仓库第一次把「板侧事实」拼给一个**非赛题**
的页面用（检测页不读题面、不进生成流程），而它的输入分别住在 wiring / pin_bindings
/ readme / boards 与 hwcheck 族的配方 / 命令台 / 通用降级里。拼装逻辑留在这里，
路由只取参转调；`hwcheck.py` 继续只管"检测程序长什么样"（纯函数、不碰盘），本模块
是它的板侧对偶。

工单 webapp-consolidation/01 起，**检测页的那一次完整投影**（`hwcheck_view`：板侧
视图 + 逐件小节 + 通用降级 + 命令台 + 互斥组 + 引脚消解）也归本模块——它原先住在
`webapp.create_app` 里（约 483 行），只能经 `TestClient` 端到端测，且每张检测页
工单都要改那个热点文件。现在的接口是**路径进 / 载荷出**（`module_library_dir` /
`masters_dir` / `recipe_path` + `HwCheckConfig`），不吃 HTTP 层的 `AppContext`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .boards import Board, board_for_platform
from .hwcheck import (
    HWCHECK_CHANNEL_LABELS,
    HWCHECK_CHANNEL_MODULES,
    HWCHECK_CHANNEL_SECTION,
    HWCHECK_DEVICE_SECTION,
    HWCHECK_FRAMEWORK_MODULES,
    HwCheckConfig,
    dedup_slugs,
    hwcheck_devices,
    hwcheck_modules,
    require_known_platform,
)
from .hwcheck_console import build_console_table, console_capacity_note, console_payload
from .hwcheck_custom import (
    PROBE_MODULE_SLUG,
    CustomPlanEntry,
    CustomSection,
    plan_order_rows,
    plan_payload as custom_plan_payload,
    resolve_custom_plan,
    resolve_custom_sections,
)
from .hwcheck_errors import HwCheckError
from .hwcheck_generic import (
    GenericSection,
    generic_message,
    resolve_generic_sections,
)
from .hwcheck_recipe import (
    RecipeSection,
    load_library_recipes,
    resolve_sections,
    sections_payload,
)
from .library import list_modules
from .manifest import ModuleManifest, collect_exclusive_groups
from .master_store import master_project_dir
from .hwcheck_store import read_custom_snapshots
from .my_devices import DEVICE_ID_PREFIX, CustomDevice, list_devices, my_devices_dir
from .pin_bindings import (
    ResolvedBinding,
    _shared_groups,
    auto_assign_bindings,
    resolve_bindings,
)
from .platforms import PLATFORM_MSPM0
from .readme import (
    BRING_UP_SLUGS,
    PIN_TABLE_FOOTNOTE,
    VERIFICATION_GUIDE,
    sort_verification_order,
)
from .selection import WARNING_MISSING, check_platform_warnings, resolve_dependencies
from .syscfg_model import MSPM0_SYSCFG_FILENAME
from .syscfg_instances import INSTANCE_CONSUMERS, instance_label
from .syscfg_prune import SyscfgPinConflictReport, syscfg_pin_conflict_report
from .wiring import wiring_rows

__all__ = [
    "HWCHECK_ORDER_REASON",
    "HWCHECK_PIN_EXIT_MARKER",
    "HwCheckBoardView",
    "HwCheckPinPlan",
    "HwCheckView",
    "hwcheck_board_view",
    "hwcheck_board_view_for",
    "hwcheck_missing_message",
    "hwcheck_pin_message",
    "hwcheck_pin_plan",
    "hwcheck_view",
]
# 「为什么是这个次序」——顺序判据本身来自 readme（bring-up 前置 + 依赖序），
# 这句话只是把它讲给学生听；页面显式展示它（票面：「在页面显式展示建议按这个
# 次序测的理由」）。文案单源在这里：页面两处（顺序区标题与脚注）共用一句。
HWCHECK_ORDER_REASON = (
    "先确认「板子活着」——延时 / 串口 / 灯这类 bring-up 模块排在最前；"
    "其余按依赖序一件一件往下测（被依赖的在前），前一件不通，后一件的现象就不可信。"
)


def hwcheck_missing_message(slug: str, platform: str) -> str:
    """「这件在本平台没有条目」的页面文案（判据在 selection，文案在检测页）。

    判据（该平台有没有这个模块的条目）走 `selection.check_platform_warnings`
    的 missing 一类——与生成侧同一处；措辞归检测页（这里说的是"无法检测"，
    生成侧说的是"生成将失败"，两种说法各自面对的场景不同）。
    """
    return (
        f"{slug}：该模块无本平台版本，无法检测"
        f"（模块库里没有它在 {platform} 上的条目）——请把它去掉，或换到它有版本的平台再测"
    )


# 检测页「装不下」文案里的**判据标记**（不是给学生的措辞：探针按它区分「如实拦下、
# 页面已说明原因」与「缺陷式静默拦下」——工单 hwcheck-pin-conflict-exit/01 的验收线）。
# 写成带方括号的哨兵而不是一整句中文：句子会被顺手改写，改了就把判据悄悄挪走。
HWCHECK_PIN_EXIT_MARKER = "【检测页出路】"


def read_master_syscfg(masters_dir: Path | str, platform: str) -> str | None:
    """母版 mspm0.syscfg 全文（检测页引脚消解用）。

    为什么要读母版这一份：装不装得下的判据 = **落盘后的 syscfg**
    （`prune(选中集) → rewrite(绑定)`），而那份文本的起点就是母版文件。

    **两种"没有这份配置"必须分开**（工单 hwcheck-hygiene/04）：

    * **平台本来就没有这份配置**（非 mspm0）／**母版没导入**（文件不在）→ `None`：
      平台不可用是页面已有的状态（导入母版那条路），容量判定跳过——但**不许无声**，
      由 `hwcheck_pin_plan` 把"没判"写进 `HwCheckPinPlan.capacity_note` 带给页面。
    * **文件在、但读不出来**（占用 / 权限 / IO）→ `HwCheckError` 400 中文：这是**失败**，
      旧实现把它也并进上面那一档 `return None`，于是"读不出来"被当成"没有这份配置"，
      预览放行、生成才 400，学生看不到任何理由——**判不了不许伪装成判过了**。
    """
    if platform != PLATFORM_MSPM0:
        return None
    path = master_project_dir(Path(masters_dir), platform) / MSPM0_SYSCFG_FILENAME
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HwCheckError(
            f"母版配置 {path.name} 读不出来：{exc} —— "
            "它可能正被别的程序占用（编辑器 / 资源管理器预览），或当前账户没有读权限；"
            "先把占用它的程序关掉（或把母版换一处放置）再试。"
        ) from exc


def _master_syscfg_for(
    masters_dir: Path | str, platform: str, *, loud: bool
) -> tuple[str | None, str]:
    """→ (母版 syscfg 文本 | None, 容量判定跳过时的人话原因)。

    `loud=True`（预览 / 生成：这一趟真要判容量）时，母版**在、读不出来** → 直接
    `HwCheckError` 400（`read_master_syscfg` 抛出）。

    `loud=False`（回读 / 排障：回放的是**已经生成成功的那一次**，容量早就判过）时，
    读不出来按"判不了就不判"走，但**照样把原因说出来**（`PIN_CAPACITY_UNREADABLE_NOTE`）
    ——母版文件被编辑器占着不该让人打不开自己的检测工程；反过来，跳过也绝不无声
    （工单 hwcheck-hygiene/04 的两条一起满足）。
    """
    try:
        text = read_master_syscfg(masters_dir, platform)
    except HwCheckError:
        if loud:
            raise
        return None, PIN_CAPACITY_UNREADABLE_NOTE
    return text, ""


# 「这一趟**没判**装不装得下」的人话说明（工单 hwcheck-hygiene/04）：母版没导入时
# 容量判定整段跳过——跳过得说出来，否则页面看起来像"检查过了、没问题"。文案归域层
# （与 `hwcheck_pin_message` 同族），前端只渲染。
#
# ⚠ 这是**页面上要显示的**话（前端 `esc()` 之后进 innerHTML）——**不许写 markdown 标记**
# （工单 hwcheck-hygiene/02 的口径：产品串里的 `**…**` 到了页面上就是两个字面星号；
# 那条守卫的面只切 `static/js/**`，**管不到这里**，所以全靠这条注释与评审盯住）。
PIN_CAPACITY_SKIPPED_NOTE = (
    "没导入 mspm0 母版（或母版里没有 mspm0.syscfg）：这一趟没判「装不装得下」"
    "——先到「母版库」把 mspm0 母版导入，再回来看这一步的结论。"
)

# 同上一句的另一种成因（工单 04）：母版**在**、但这次读不出来。回读 / 排障那条路
# （`require_pins=False`，工程已经生成成功了）按"判不了就不判"走，但**照样说出来**：
# 学生不至于因为母版文件被编辑器占着就打不开自己的检测工程。
PIN_CAPACITY_UNREADABLE_NOTE = (
    "母版 mspm0.syscfg 这次读不出来（可能被别的程序占用）：这一趟没判「装不装得下」"
    "——关掉占用它的程序再刷新，这一句就没了。"
)


@dataclass(frozen=True)
class HwCheckPinPlan:
    """检测页的引脚消解结果（工单 hwcheck-pin-conflict-exit/01）。

    `bindings` = 增量（自动让位的角色 → 新脚），原样喂生成内核（工程 README /
    接线快照因此与页面同源）；`resolved` = 校验后的绑定（接线表 / 冲突组按它渲染）；
    `fixed` = 「动了哪几根线」的人话说明行；`conflict` = 装不下时的页面文案
    （空串 = 这一趟能生成）；`capacity_note` = 「这一趟没判容量」的原因
    （非空 = 判不了，且**页面看得见**；工单 hwcheck-hygiene/04）。
    """

    bindings: dict[str, str] = field(default_factory=dict)
    resolved: tuple[ResolvedBinding, ...] = ()
    fixed: tuple[str, ...] = ()
    conflict: str = ""
    capacity_note: str = ""

    @property
    def ok(self) -> bool:
        return not self.conflict


def hwcheck_pin_plan(
    platform: str,
    manifests: Sequence[ModuleManifest],
    board: Board,
    master_syscfg: str | None,
    config: HwCheckConfig,
    *,
    capacity_note: str = "",
) -> HwCheckPinPlan:
    """检测页生成前的引脚消解（纯函数：吃已解析的 manifest / 板 / 母版 syscfg 文本）。

    两步，判据全部复用既有单源：

    1. **自动解冲突** = `auto_assign_bindings(resolve_default_conflicts=True)`
       ——与赛题页「自动配置」按钮同一个求解器、同一个开关；只动真冲突的角色，
       合法共享（含薄封装共读同槽）不动。
    2. **装不装得下** = `syscfg_prune.syscfg_pin_conflict_report`（落盘文本的同脚
       多实例冲突）——与生成门禁**同一个函数**，所以「预览通过 → 生成 400」这类
       分家不可能再出现；装不下时给出检测页能执行的出路（`hwcheck_pin_message`）。

    `config`（工单 hwcheck-acceptance/03）= **页面上那一趟选择本身**（两个通道勾选
    框 + 器件清单）：出口文案要说"取消勾选哪个通道 / 去掉哪件器件"，那一步的判据
    就是它（同一个 `oled` 模块，勾着通道时它是通道、只从器件列表里选时它是器件）
    ——所以这里必须吃配置，不能只吃 manifests。

    **只对 mspm0 自动搬**：stm32 的默认脚重叠按 ADR 0010 是提示语义、不拦生成，
    搬了反而改掉既有工程（逐字节回归），故 stm32 返回空计划。
    `master_syscfg` 缺失（母版没导入 / 假母版）= 判不了就不判，只做第 1 步——
    但**跳过得说出来**：`capacity_note` 默认取 `PIN_CAPACITY_SKIPPED_NOTE`（母版没导入），
    调用方有更精确的成因就传进来（回读 / 排障那条路传"读不出来"那一句）。
    而"母版在、读不出来"在**需要判容量**的路径上（`require_pins=True`）于
    `read_master_syscfg` 那一步就 400 了，不会走到这里。
    """
    if platform != PLATFORM_MSPM0:
        return HwCheckPinPlan()
    solved = auto_assign_bindings(
        manifests, platform, board, {}, resolve_default_conflicts=True
    )
    resolved = (
        resolve_bindings(manifests, platform, board, solved.bindings)
        if solved.bindings
        else ()
    )
    if not master_syscfg:
        return HwCheckPinPlan(
            dict(solved.bindings), resolved, solved.fixed,
            capacity_note=capacity_note or PIN_CAPACITY_SKIPPED_NOTE,
        )
    report = syscfg_pin_conflict_report(
        master_syscfg=master_syscfg,
        manifests=manifests,
        platform=platform,
        board=board,
        bindings=solved.bindings,
        # 容量诊断的基准 = 用户这一趟的选择本身（bindings 为空），不是自动搬过
        # 一遍之后的增量——否则"本来能解开几组"会读成 0（见 report 的 docstring）。
        diagnosis_bindings={},
    )
    if not report.conflict_count:
        return HwCheckPinPlan(dict(solved.bindings), resolved, solved.fixed)
    return HwCheckPinPlan(
        dict(solved.bindings),
        resolved,
        solved.fixed,
        hwcheck_pin_message(report, board.name, config),
    )


def hwcheck_pin_message(
    report: SyscfgPinConflictReport, board_name: str, config: HwCheckConfig
) -> str:
    """「这套选择装不下」的页面文案（**检测页**出路，不是赛题页那句话）。

    为什么必须单独一句：检测页没有引脚配置入口，生成门禁那句「在引脚配置里改绑
    （或点自动配置）」对学生是不可执行的指令（本单的由来）。所以这里给几条
    检测页做得到的动作，把「去赛题页改绑」降为最后一条而不是唯一一条。

    **两根轴两套话**（工单 11）：同脚冲突有容量数字可讲（脚不够 / 改绑解得开几组），
    而**同名引脚符号**与脚数无关——撞的是 `$name`，改绑解不开，出路是去掉一件或
    改母版名。所以那一支**不套容量诊断**，直接点名是哪两件模块撞了。

    **出路按成因分派到页面控件**（工单 hwcheck-acceptance/03）：撞的实例属于某个
    **输出通道**（勾选框在「2. 输出通道」）就说"取消勾选那个通道"；属于**器件清单**
    里的某一件就说"去掉这一件"。SysConfig 实例名只作括号里的补充信息——旧文案把人
    支去"上面的器件选择"，可 `oled` 根本不在器件列表里（它是通道勾选框），学生照着
    做走不通。分派判据是**现算**的（`_page_action_lines`：通道开关 + 通道模块 +
    `INSTANCE_CONSUMERS` 反查），不抄实例名清单。

    `board_name` 由调用方传（板上就那一块板，`hwcheck_pin_plan` 手里有板对象）
    ——板名是单源事实（`boards/*.json`），不在这句话里另写一份；容量诊断段自己
    也用同一份板名，两处必须同一块板。
    文案里的 `HWCHECK_PIN_EXIT_MARKER` 是判据哨兵（见常量说明）。
    """
    actions = _page_action_lines(report, config)
    numbered = "\n".join(
        f"  {index}. {line}" for index, line in enumerate(actions, start=1)
    )
    last = f"  {len(actions) + 1}. "
    if not report.lines:
        return (
            f"这套选择在「{board_name}」上装不下：落盘后的 mspm0.syscfg 里 "
            f"{report.name_count} 个引脚<strong>符号</strong>被两只实例同时使用，SysConfig 会"
            "直接报 Duplicate name（工程编不过）：\n"
            + "\n".join(report.name_lines)
            + "\n这一条<strong>改绑引脚解不开</strong>（撞的是符号名，不是脚——母版给这些实例起的"
            "引脚符号本来就同名；实测换四种绑定 `name_count` 恒为 2）。"
            + f"\n{HWCHECK_PIN_EXIT_MARKER} 检测页能做到的出路（挑一条）：\n"
            + numbered
            + f"\n{last}上面这些都要 → 改绑这一页做不到（撞的是<strong>符号名</strong>，不是脚；"
            "母版里的符号名得改成每个实例各不相同才行）——别去引脚配置里试，"
            "改绑解不开它。"
        )
    return (
        f"这套选择在「{board_name}」上装不下：落盘后的 mspm0.syscfg 有 "
        f"{report.pin_count} 个引脚被两只实例同时占用，SysConfig 会直接报 "
        "Resource conflict（工程编不过）。自动移脚已经尽力，剩下的靠改绑解不开：\n"
        + "\n".join(report.lines)
        + report.capacity
        + f"\n{HWCHECK_PIN_EXIT_MARKER} 检测页能做到的出路（挑一条）：\n"
        + numbered
        + f"\n{last}上面这些都要 → 先到「做题」页的引脚配置里把它们分开，"
        "再回来生成（检测页暂时没有改绑入口）。"
    )


def _page_action_lines(
    report: SyscfgPinConflictReport, config: HwCheckConfig
) -> tuple[str, ...]:
    """出口文案里**点名页面控件**的那几条（工单 hwcheck-acceptance/03）。

    判据 = "这一趟页面上哪些控件能把这些实例从工程里拿掉"，全部现算：

    * **输出通道**：实例的消费模块 = 某个**开着**的通道的模块（`HWCHECK_CHANNEL_MODULES`）
      → "取消勾选「2. 输出通道」里的「OLED 屏」"（勾选框的文字单源在
      `HWCHECK_CHANNEL_LABELS`，与 index.html 对过账）；
    * **器件清单**：实例的消费模块在 `hwcheck_devices(config)` 里 → "去掉
      「3. 要测的器件」里的 aht10 这一件"（页面上的 chip 印的就是这个 slug）；
    * **都不是**（检测框架自带的心跳 led / delay，或别的器件带进来的依赖 / 母版没登记
      归属的新实例）→ 如实说它不在这一页的勾选框里，别编一个做不到的动作。

    ⚠ 框架模块（`HWCHECK_FRAMEWORK_MODULES`）**不算器件**：它恒在工程里，从器件
    列表里点掉也不影响这一趟——把它算作"器件"会让学生照着点、点完照旧 400。

    实例名与它属于哪条通道/哪件器件都是 `syscfg_instances` 单源（`instance_label`
    + `INSTANCE_CONSUMERS`），只作括号里的补充信息。
    """
    instances = tuple(
        dict.fromkeys((*report.pin_instances, *report.name_instances))
    )
    selected = hwcheck_devices(config)
    owned: dict[str, list[str]] = {}        # 控件 → 它带进来的实例
    devices: dict[str, list[str]] = {}      # 器件 slug → 它带进来的实例
    orphans: list[str] = []                 # 这一页没有控件能单独拿掉的实例
    # 孤儿实例的**三种成因分开记**（评审整改）：说错成因比不点名更坏——
    # 学生会照着一条做不到的动作去点。
    framework_orphans: list[str] = []       # 只由框架模块（led / delay）带进来
    dependency_orphans: list[str] = []      # 由别的器件的依赖带进来
    unregistered_orphans: list[str] = []    # 母版里根本没登记归属（新加的实例）
    for instance in instances:
        consumers = INSTANCE_CONSUMERS.get(instance, ())
        channels = [
            channel
            for channel, module in HWCHECK_CHANNEL_MODULES.items()
            if getattr(config, channel) and module in consumers
        ]
        # 框架模块不算"器件在清单里"：它在工程里恒存在（见上面 docstring）
        hits = [
            slug
            for slug in selected
            if slug in consumers and slug not in HWCHECK_FRAMEWORK_MODULES
        ]
        for channel in channels:
            owned.setdefault(channel, []).append(instance)
        for slug in hits:
            devices.setdefault(slug, []).append(instance)
        if not channels and not hits:
            orphans.append(instance)
            if not consumers:
                # INSTANCE_CONSUMERS 里没有它 = 判据不认识的实例。**不能**说它是
                # "检测程序自带的心跳模块"——那是另一回事（consumers 只含框架模块）。
                unregistered_orphans.append(instance)
            elif all(slug in HWCHECK_FRAMEWORK_MODULES for slug in consumers):
                framework_orphans.append(instance)
            else:
                dependency_orphans.append(instance)

    lines: list[str] = []
    if owned:
        # 按**页面上的勾选框顺序**（`HWCHECK_CHANNEL_MODULES`）点名，不按实例出现序
        labels = "、".join(
            f"「{HWCHECK_CHANNEL_LABELS[channel]}」"
            for channel in HWCHECK_CHANNEL_MODULES
            if channel in owned
        )
        owned_instances = [i for channel in HWCHECK_CHANNEL_MODULES
                           for i in owned.get(channel, ())]
        lines.append(
            f"取消勾选「{HWCHECK_CHANNEL_SECTION}」里的{labels}再生成"
            f"（撞上的实例：{_instances_note(owned_instances)}）；"
        )
    if devices:
        # 同上：按器件清单里的**选择顺序**（`hwcheck_devices`，页面上 chip 的顺序）
        slugs = "、".join(slug for slug in selected if slug in devices)
        device_instances = [i for slug in selected for i in devices.get(slug, ())]
        lines.append(
            f"去掉「{HWCHECK_DEVICE_SECTION}」里勾上的 {slugs} 再生成"
            f"（撞上的实例：{_instances_note(device_instances)}）；"
        )
    if framework_orphans:
        lines.append(
            f"上面点名的 {_instances_note(framework_orphans)} 是检测程序自带的"
            "心跳模块（led / delay），这一页去不掉它——换一件落点不撞的器件再生成；"
        )
    if dependency_orphans:
        lines.append(
            f"上面点名的 {_instances_note(dependency_orphans)} 在"
            f"「{HWCHECK_DEVICE_SECTION}」里没有它自己"
            "（是别的器件带进来的依赖）——去掉带它进来的那一件器件，"
            "或换一件落点不撞的；"
        )
    if unregistered_orphans:
        # 未登记实例（母版新增、判据表还没跟上）：**如实说这一页没有对应控件**，
        # 不编一个"去掉某件"的动作（学生在这一页上找不到它）。
        lines.append(
            f"上面点名的 {_instances_note(unregistered_orphans)} 是母版新加的实例，"
            "这一页没有对应的勾选控件——换一件落点不撞的器件，或先把这组选择"
            "报给维护者（母版实例归属表还没登记它）；"
        )
    if not lines:
        # 兜底（报告说冲突、却一只实例都没登记）：**仍然只点这一页真有的控件**。
        # ⚠ 不许写回工单 03 点名删掉的那句"回到上面的器件选择，去掉一件"——它把
        # 只存在于器件清单之外的实例（输出通道）也支到器件列表里，做不到。
        lines.append(
            f"这一趟装不下：先取消勾选「{HWCHECK_CHANNEL_SECTION}」里的通道，"
            f"或去掉「{HWCHECK_DEVICE_SECTION}」里勾上的一件器件，再生成；"
        )
    return tuple(lines)


def _instances_note(instances: Sequence[str]) -> str:
    """实例清单 → 「oled(OLED_SPI)、jy61p(JY61P)」（人读标签单源）。

    只作**括号里的补充信息**（工单 hwcheck-acceptance/03）：学生按页面控件动作，
    对不上号时再看这几个实例名——所以它永远跟在一条点名控件的出路后面，不单独成句。
    """
    return "、".join(instance_label(instance) for instance in instances)


@dataclass(frozen=True)
class HwCheckBoardView:
    """检测页板侧视图（一次算好，前端只渲染，不重算任何判据）。

    rows = 接线行（`wiring_rows` 的字段 + `pin_note` 板上注记，空串 = 板上没说）；
    groups = 模块之间的同脚组（`_shared_groups` 原样：pin / roles / kind / reason）；
    board_shares = **板上自带**的共享脚（选中模块用到了板上已经接着别的东西的脚，
    如地猛星 PA0/PA1 与板载 LED 同脚）——`_shared_groups` 只看模块角色，
    看不见这类"板子自己就接好了"的重叠，故单独一列，否则冲突区会给出假安心；
    order = 建议顺序 [{slug, description, bring_up}]；
    missing = 本平台没有条目的**选中器件** [{slug, message}]（点名，不静默省略）；
    pin_fixes（工单 hwcheck-pin-conflict-exit/01）= 生成前自动移开的默认脚撞脚
    （人话说明行，空 = 一根都没动）——页面要把"动了哪几根线"如实打在接线表旁边，
    学生照表接线的前提是表本身是新脚；
    guide / footnote = 与工程 README 同源的引导语与尾注；reason = 为什么按这个次序。
    """

    rows: tuple[dict, ...]
    groups: tuple[dict, ...]
    board_shares: tuple[dict, ...]
    order: tuple[dict, ...]
    missing: tuple[dict, ...]
    guide: str = VERIFICATION_GUIDE
    reason: str = HWCHECK_ORDER_REASON
    footnote: str = PIN_TABLE_FOOTNOTE
    pin_fixes: tuple[str, ...] = ()
    # 「这一趟没判装不装得下」的原因（工单 hwcheck-hygiene/04）：非空 = 判不了。
    # 与 `pin_fixes` 同层（都在 `wiring` 载荷里），页面在同一块里渲染。
    capacity_note: str = ""

    def to_dict(self) -> dict:
        """JSON 载荷形态（preview / generate / project 三个端点共用一处投影）。"""
        return {
            "rows": [dict(row) for row in self.rows],
            "groups": [dict(group) for group in self.groups],
            "board_shares": [dict(item) for item in self.board_shares],
            "order": [dict(item) for item in self.order],
            "missing": [dict(item) for item in self.missing],
            "pin_fixes": list(self.pin_fixes),
            "capacity_note": self.capacity_note,
            "guide": self.guide,
            "reason": self.reason,
            "footnote": self.footnote,
        }


def hwcheck_board_view(
    platform: str,
    manifests: Sequence[ModuleManifest],
    board: Board,
    *,
    devices: Sequence[str] = (),
    resolved_bindings: Sequence[ResolvedBinding] = (),
    pin_fixes: Sequence[str] = (),
    capacity_note: str = "",
    custom_device_ids: Sequence[str] = (),
) -> HwCheckBoardView:
    """投影一次（纯函数：吃已解析的 manifest 集与板定义，不碰盘）。

    `manifests` = 依赖展开后的集合（`resolve_dependencies` 的结果，顺序即进工程
    顺序）——调用方与生成内核吃的是同一个集合，接线行/顺序因此与工程 README 同源。
    `devices` = 用户选中的器件（判"本平台有没有条目"用；不传 = 不报缺，
    框架与通道模块的缺条目属于环境坏，由生成侧大声失败）。
    `resolved_bindings` / `pin_fixes`（工单 hwcheck-pin-conflict-exit/01）=
    `hwcheck_pin_plan` 的消解结果：接线行按**生效脚**渲染、冲突组按生效布局判
    （学生照页面接线，页面的脚必须与工程 README 一致），`pin_fixes` 原样带给页面。
    `custom_device_ids`（工单 02）= 自建件——它们**不是模块**，所以既不算"本平台
    没有条目"（那会点错名：它不是缺版本，是根本还没接进渲染），也不再往下游走。
    """
    pin_notes: dict[str, str] = {}
    for pin in board.pins:
        if pin.notes and pin.name not in pin_notes:
            pin_notes[pin.name] = pin.notes

    rows = tuple(
        {**row, "pin_note": pin_notes.get(row["pin"], "")}
        for row in wiring_rows(platform, manifests, resolved_bindings)
    )
    order = tuple(
        {
            "slug": manifest.slug,
            "description": manifest.description,
            "bring_up": manifest.slug in BRING_UP_SLUGS,
        }
        for manifest in sort_verification_order(manifests)
    )
    pins = {
        row["pin"]: str(row.get("pin_note") or "").strip()
        for row in rows
    }
    return HwCheckBoardView(
        rows=rows,
        groups=_shared_groups(
            manifests, platform, board,
            {binding.role_key: binding.pin for binding in resolved_bindings},
        ),
        board_shares=_board_shares(rows),
        order=order,
        missing=_missing_devices(
            platform, manifests, devices, custom_device_ids=custom_device_ids
        ),
        pin_fixes=_pin_fixes(pin_fixes, resolved_bindings, pins),
        capacity_note=str(capacity_note or ""),
    )


def _pin_fixes(
    fixes: Sequence[str],
    resolved_bindings: Sequence[ResolvedBinding],
    pin_notes: Mapping[str, str],
) -> tuple[str, ...]:
    """「生成前动过哪几根线」的载荷行（求解器说明行 + 新脚上的板载注记）。

    说明行由 `hwcheck_pin_plan` 给（求解器原话）。这里再补一句**板载注记**：
    自动移脚可能把某根线落到板子本来就接着别的东西的脚上（地猛星 PA0/PA1 与板载
    LED 同脚、PA2 与 KEY START 同脚）——只看顶部提示的学生会漏掉接线表那一行的 ⚠。
    注记取自同一份 `BoardPin.notes`（接线表 `pin_note` 的来源），不另编一句话。
    """
    extra = [
        f"{binding.role_key} → {binding.pin}：这根脚板上有注记——{note}"
        "（下面接线表那一行也标着）"
        for binding in resolved_bindings
        if (note := (pin_notes.get(binding.pin) or "").strip())
    ]
    return (*fixes, *extra)


def _board_shares(rows: Sequence[dict]) -> tuple[dict, ...]:
    """板上自带的共享脚：由接线行的 `pin_note` 归并（pin → 注记 + 用到它的角色）。

    判据 = 板定义自己写了注记（`BoardPin.notes`，如地猛星 PA0/PA1 的「板载 LED
    共用（I2C_0 SDA，通信期间微闪）」）——本函数只做归并，不判断"这算不算冲突"
    （板上怎么接的是硬件事实，页面照抄）。行序即出现序（确定性）。
    """
    merged: dict[str, dict] = {}
    for row in rows:
        note = str(row.get("pin_note") or "").strip()
        if not note:
            continue
        pin = str(row.get("pin") or "")
        entry = merged.setdefault(pin, {"pin": pin, "note": note, "roles": []})
        role = f"{row.get('slug', '')}.{row.get('role_id', '')}"
        if role not in entry["roles"]:
            entry["roles"].append(role)
    return tuple(merged.values())


def _custom_devices_for(
    data_dir: Path | str, config: HwCheckConfig, snapshot_dir: Path | str | None = None
) -> tuple[tuple[CustomDevice, ...], frozenset[str]]:
    """这一趟**选中的**自建件定义（按 `config.devices` 里的 id 读）＋ 快照来源集。

    只读选中的那几件：收藏里躺着的不进这一趟（也不该让一次预览去扫整个数据目录
    ——读一件失败会让整页 400，而那件根本没参与这次检测）。
    读不出来（条目坏了 / 已被删）= 大声失败（`list_devices` 的既定约定）——
    静默跳过会让"我明明选了它"变成一次悄无声息的少测。

    **快照优先**（工单 hwcheck-unknown-device/08）：给了 `snapshot_dir`（工程
    目录）且选中的**每一件自建件**都有工程内快照时，回读吃快照——用户之后改了
    或删了「我的器件」不影响已生成的工程。⚠ 快照门只判**自建件子集**（`mine_`
    前缀是两类东西的分界，库内件不归档也没有快照）——拿全量选中集判 `all()`
    的第一版在混选（自建件 + 任意库内件）时永远走不进快照分支，被评审当场抓红。
    部分 / 全部没有快照（08 之前的工程）→ 照旧走数据目录（行上的 `snapshot`
    标记据此如实标）。返回 `(定义, 来自快照的 id 集)`。
    """
    root = my_devices_dir(data_dir)
    wanted = hwcheck_devices(config)
    if not wanted:
        return (), frozenset()
    if snapshot_dir is not None:
        custom_ids = [
            slug for slug in wanted if slug.startswith(DEVICE_ID_PREFIX)
        ]
        snapshots = read_custom_snapshots(snapshot_dir, custom_ids)
        if custom_ids and all(slug in snapshots for slug in custom_ids):
            return (
                tuple(snapshots[slug] for slug in custom_ids),
                frozenset(snapshots),
            )
    known = {device.id: device for device in list_devices(root)}
    return (
        tuple(known[slug] for slug in wanted if slug in known),
        frozenset(),
    )


def _missing_devices(
    platform: str,
    manifests: Sequence[ModuleManifest],
    devices: Sequence[str],
    *,
    custom_device_ids: Sequence[str] = (),
) -> tuple[dict, ...]:
    """选中器件里本平台没有条目的那些（判据 = selection 的平台警告表）。

    保序去重（用户点选的顺序，`dedup_slugs` 单源），逐条给中文文案——**点名，
    不静默省略**：悄悄从接线表里消失会让学生以为"选上了、待会儿就能测"。

    自建件（`custom_device_ids`）先摘掉：它们不是"本平台没有条目"，是**还不是模块**
    （工单 02 只打通事实那条路，接进渲染是工单 03）——混进来会点一个错名。
    传进来的集合应已与 `devices` 取过交集（`hwcheck_view` 那一层做），所以这里的
    逐条判断只按 id 比一次。
    """
    custom = set(custom_device_ids)
    wanted = [slug for slug in dedup_slugs(devices) if slug not in custom]
    if not wanted:
        return ()
    by_slug = {manifest.slug: manifest for manifest in manifests}
    warnings = check_platform_warnings(wanted, platform, by_slug)
    return tuple(
        {"slug": warning.slug, "message": hwcheck_missing_message(warning.slug, platform)}
        for warning in warnings
        if warning.kind == WARNING_MISSING
    )


def hwcheck_board_view_for(
    module_library_dir: Path | str,
    platform: str,
    slugs: Sequence[str],
    *,
    devices: Sequence[str] = (),
) -> HwCheckBoardView:
    """路由侧入口：库根 + 平台 + 模块集 → 视图（读库、展开依赖、取板定义）。

    读盘只在这里（`hwcheck_board_view` 本身是纯的，可内存直测）；库外 slug 由
    `resolve_dependencies` 大声失败（UnknownModuleError 已登记 400），不静默当空。
    """
    # 板定义按平台取：词表校验与 HwCheckConfig 同一句（require_known_platform），
    # 直接调本函数的调用方不会拿到 BoardError 的 500
    require_known_platform(platform)
    by_slug = {manifest.slug: manifest for manifest in list_modules(Path(module_library_dir))}
    manifests = resolve_dependencies(list(slugs), by_slug)
    return hwcheck_board_view(
        platform, manifests, board_for_platform(platform), devices=devices
    )


@dataclass(frozen=True)
class HwCheckView:
    """检测页的**一次投影**（工单 webapp-consolidation/01：装配从 webapp 搬回域层）。

    字段各是各的东西，所以具名而不是塞一个 dict：

    * `board` = 载荷的键（`wiring` / `sections` / `console` / `unspecialized` /
      `exclusive_groups` / `custom`，端点用 `**view.board` 展开；「动了哪几根线」的
      `pin_fixes` 住在 `wiring` 里，不是顶层键——前端读的也是 `wiring.pin_fixes`）；
    * `sections` / `generic` / `custom` = 域层对象（生成端点还要拿它们去渲染 main.c，
      不必再解析一遍）；
    * `custom_plan` = 自建件的**检测页计划**（`CustomPlanEntry`，工单 05）：选中的
      每一件都在（含不出小节的那几件），页面读它、`board["custom"]` 是它的载荷；
      与 `custom` 的关系 = "计划里出小节的那几件"（`probes` 判据单源）；
    * `pin_bindings` = 自动消解出的绑定增量（生成端点原样喂生成内核——页面接线表与
      工程 README 同源的前提）；
    * `known_slugs` = 整库模块 slug（排障的事实约束判据用，**不进任何载荷**）；
    * `generation_slugs` = 这一趟**真正要进工程的 slug 集**（`hwcheck_modules` 去掉
      自建件、有自建件小节时补上 `i2c_probe`）。生成端点必须吃它——吃
      `hwcheck_modules(config)` 会把 `mine_*` 当模块送进生成链、在
      `resolve_dependencies` 那里 400，而**预览走本模块的局部 manifests 所以看不出
      来**：同一条判据两处各算一遍，就是"预览 200 → 生成 400"（本单实测踩到）。
    """

    board: dict[str, Any]
    sections: tuple[RecipeSection, ...]
    generic: tuple[GenericSection, ...]
    custom: tuple[CustomSection, ...]
    custom_plan: tuple[CustomPlanEntry, ...]
    pin_bindings: dict[str, str]
    known_slugs: tuple[str, ...]
    generation_slugs: tuple[str, ...]
    # 选中的自建件里**已经从器件库消失**的那些（工单 ci-gate-fixes/09）：装配时摘掉
    # （否则整页 400），端点把这份清单带给页面，页面如实说一句"已不在你的器件里"。
    dropped_devices: tuple[str, ...] = ()


def hwcheck_view(
    config: HwCheckConfig,
    *,
    module_library_dir: Path | str,
    masters_dir: Path | str,
    recipe_path: Path | str | None = None,
    require_pins: bool = True,
    data_dir: Path | str | None = None,
    custom_snapshot_dir: Path | str | None = None,
) -> HwCheckView:
    """检测页装配的唯一出处：路径 + 配置进，一次投影出。

    四个端点（preview / generate / project / triage）共用这一处装配：读库一次
    → 展开依赖（`resolve_dependencies` 的顺序即进工程顺序）→ 配方装载
    （`load_library_recipes`）→ **引脚消解**（`hwcheck_pin_plan`，工单
    hwcheck-pin-conflict-exit/01：检测页没有引脚配置入口，默认脚撞脚在这里就解开）
    → 板侧投影（`hwcheck_board_view`）→ 小节解析（`resolve_sections`，顺序走既有
    bring-up 排序）→ **通用降级小节**（`resolve_generic_sections`，工单 07：专精件
    之外的那些件，判据全在库内已声明的事实上）。各端点各拼一遍就是三份判据来源，
    迟早漂。

    **接口吃显式路径与配置对象，不吃 HTTP 层的 AppContext**（工单
    webapp-consolidation/01）：所以本函数脱离 `TestClient` 可直测，也不必知道"配置
    从哪儿来"。库路径缺失的 400 归调用方（路由侧取配置那一步），不在这里。

    库外 slug 由 `resolve_dependencies` 大声失败（UnknownModuleError 已登记 400）；
    配方坏了由 `load_library_recipes` 大声失败（HwCheckError 400 中文）——两条都不
    静默，也**不许**为了"至少能出接线表"而降级成跳过（那会让坏配方悄悄溜过去）。
    装不下（自动移脚后仍撞脚）由 `require_pins` 控：预览与生成**同一判据**（都
    400），回读端点不算（它回放的是已经生成成功的那一次）。

    `data_dir`（工单 hwcheck-unknown-device/02-03）= **工具数据目录**（HTTP 层 =
    `AppContext.config_path.parent`）；给了才读「我的器件」并解析自建件小节。
    自建件**不进 slugs**（它们是数据、不是模块：没有 manifest，库外 slug 会在生成
    链上游被 `UnknownModuleError` 拒），所以这里把它们从"要进工程的模块"里摘掉，
    并在真有自建件小节时**自动带上 `i2c_probe`**（探测代码要调它的接口——生成门禁
    要求"调的函数在被选模块头里真实存在"）。同时**不放松** `resolve_dependencies`
    对真·库外 slug 的守卫：容忍自建件与容忍手滑写错是两件事（对照组判据见
    `tests/test_my_devices_endpoint.py`）。不给 `data_dir` = 没有自建件（旧调用方
    与纯板侧测试照旧，零行为变化）。
    """
    library = Path(module_library_dir)
    by_slug = {m.slug: m for m in list_modules(library)}
    # 自建件小节（工单 03）：只有给了数据目录才读（没给 = 这一趟没有自建件）。
    # 读盘只在这一处：四个端点共用同一次装配，页面上说的与 main.c 里做的是同一份。
    # `custom_snapshot_dir`（工单 08）= 工程目录：回读时**以工程内快照为准**。
    custom_devices: tuple[CustomDevice, ...] = ()
    snapshot_ids: frozenset[str] = frozenset()
    custom_sections: tuple[CustomSection, ...] = ()
    if data_dir is not None:
        custom_devices, snapshot_ids = _custom_devices_for(
            data_dir, config, snapshot_dir=custom_snapshot_dir
        )
        custom_sections = resolve_custom_sections(
            custom_devices, has_output_channel=config.has_output_channel
        )
    # 选中的自建件**全体**都要从模块集里摘掉（不只是"出了小节"的那几件）：
    # 它们不是模块（没有 manifest），漏一件就会在 `resolve_dependencies` 那里
    # 报"库中没有这个模块"——非 I2C 件与"没勾输出通道"的形态正是这样漏出去的。
    #
    # ⚠ **「全体」包含"已经被删掉的那几件"**（工单 ci-gate-fixes/09）：选择集是从前端
    # （以及"回读上一次检测工程"那条路）来的，用户完全可能先把自建件删了、选择集里
    # 还留着它。旧写法取的是**交集**（`known_custom & set(selected)`）——只摘掉"还在
    # 器件库里"的那些，于是已删的那件一路滑进 `resolve_dependencies`，报出
    # 「库中不存在模块：mine_xxx」：那句话**指错了地方**（`mine_*` 从来不是库内模块，
    # 用户也没处去"库里"找它），整页预览就此卡死，唯一出路是手动把那个 chip 去掉。
    # 现在**摘掉并如实报出**（`dropped_devices` → 页面写明"已不在你的器件里"）。
    # 守卫**不放松**：非 `mine_` 前缀的库外 slug 照旧大声 400（那是手滑写错，不是删除）。
    selected = hwcheck_devices(config)
    known_custom = {device.id for device in custom_devices}
    dropped_custom = tuple(
        slug for slug in selected
        if slug.startswith(DEVICE_ID_PREFIX)
        and slug not in by_slug
        and slug not in known_custom
    )
    custom = known_custom & set(selected)
    excluded = custom | set(dropped_custom)
    module_slugs = [slug for slug in hwcheck_modules(config) if slug not in excluded]
    # 有自建件小节 → 探测代码要调 `i2c_probe` 的接口，它必须在模块集里（否则
    # 生成门禁判"调了不存在的函数"，mspm0 上更是连编译都过不去）。
    if custom_sections and PROBE_MODULE_SLUG not in module_slugs:
        module_slugs.append(PROBE_MODULE_SLUG)
    manifests = resolve_dependencies(module_slugs, by_slug)
    recipes = load_library_recipes(
        library, masters_dir, list(by_slug.values()), recipe_path=recipe_path
    )
    devices = selected
    board = board_for_platform(config.platform)
    master_syscfg, capacity_note = _master_syscfg_for(
        masters_dir, config.platform, loud=require_pins
    )
    plan = hwcheck_pin_plan(
        config.platform,
        manifests,
        board,
        master_syscfg,
        config,
        capacity_note=capacity_note,
    )
    if require_pins and not plan.ok:
        raise HwCheckError(plan.conflict)
    view = hwcheck_board_view(
        config.platform,
        manifests,
        board,
        devices=devices,
        resolved_bindings=plan.resolved,
        pin_fixes=plan.fixed,
        # 「这一趟没判装不装得下」交给页面说（工单 hwcheck-hygiene/04）：跳过得说出来
        # ——否则页面看起来像"检查过了、没问题"，而学生点到「生成」才吃 400。
        capacity_note=plan.capacity_note,
        # 自建件的豁免集 = **还在库里的 ∪ 已经被删掉的**（工单 ci-gate-fixes/09）：
        # `_missing_devices` 拿它把"自建件"从"本平台没有条目的库内模块"里摘出来——
        # 已删的那件同样是"还不是模块"，不摘就会在这里抛「库中不存在模块」，
        # 整页照样 400（这是本单的第二处，第一处是上面的 `module_slugs`）。
        custom_device_ids=excluded,
    )
    # 自建件的**检测页计划**（工单 05）：选中的每一件都在，出不出的来小节由
    # `hwcheck_custom` 那一处判（`resolve_custom_plan` → `_probes`，与上面 `custom`
    # 同一判据）。脚**取自板侧视图的接线行**（支点那一行，含引脚消解后的生效脚）
    # ——本模块只做投影，不重推任何一根线的落点。
    custom_plan = resolve_custom_plan(
        custom_devices,
        has_output_channel=config.has_output_channel,
        probe_rows=[
            row for row in view.rows if row.get("slug") == PROBE_MODULE_SLUG
        ],
    )
    board_payload = view.to_dict()
    # 建议顺序（工单 05）：库内那份照旧（`sort_verification_order`，判据不动），
    # 自建件**接在它后面**——"库内验证过的在前、按你给的事实试的在最后"。
    board_payload["order"] = [*board_payload["order"], *plan_order_rows(custom_plan)]
    custom_payload = custom_plan_payload(custom_plan)
    # 出处标记（工单 hwcheck-unknown-device/08）：这一行的定义来自**工程内快照**
    # 还是**数据目录现读**；快照行还要如实说「我的器件」里那条还在不在——已删的
    # 件照常显示（以快照为准），页面上点名"这是快照"，不静默也不报错。
    data_root = my_devices_dir(data_dir) if data_dir is not None else None
    for row in custom_payload:
        slug = row.get("slug", "")
        row["snapshot"] = slug in snapshot_ids
        row["stored"] = bool(data_root and (data_root / slug).is_dir())
    sections = resolve_sections(config.platform, devices, recipes, manifests)
    specialized = {section.slug for section in sections}
    # 通用降级（工单 07）：专精件之外、且在本平台有条目的那些件。没有本平台
    # 条目的件由 view.missing 那条路点名（两处都说一遍 = 两个口径）。
    generic = resolve_generic_sections(
        config.platform, devices, specialized, manifests, library
    )
    # 串口命令台（工单 06）：页面与产物读**同一张表**（`build_console_table`
    # 是纯函数，这里与 `render_main_c` 各建一次，逐字相同）。冲突照旧在这里
    # 就红 → 400 中文，学生不必等到点「生成」才知道两个器件抢了同一个字符。
    # 两批进表：**专精小节**（配方声明字符）与**自建件**（工单
    # hwcheck-unknown-device/06：没有配方，字符由命令空间分配——复用同一处
    # 保留字 / 形状 / 判重判据，复测入口是它们自己的小节函数，所以页面给的字符与
    # 产物里那条 `case` 必然是同一个）。通用件不进表（没有配方自然没有命令字符，
    # 07 的接口备忘）。
    console = build_console_table(sections, custom_sections)
    return HwCheckView(
        board={
            "wiring": board_payload,
            # 小节载荷里的命令字符 = **分配后**的那一个（工单 hwcheck-specialize/01）：
            # 首选被别的器件占了时会按候选让位，页面必须跟着表走（不然两件都写着
            # "敲 l 复测"，只有一件是真的）。
            "sections": sections_payload(
                sections,
                {
                    entry.slug: entry.command
                    for entry in console.entries
                    if not entry.custom
                },
            ),
            "console": console_payload(config.debug_uart, console),
            # 复测字符的**事前**余量提示（工单 hwcheck-hardening/05）：接近上限时页面先吭一声，
            # 不必等按了「生成」才吃 400。文案单源在 hwcheck_console，前端只渲染。
            "console_note": console_capacity_note(sections, custom_sections),
            "unspecialized": [
                {
                    "slug": section.slug,
                    "label": section.label,
                    "plan": section.plan_text,
                    "message": generic_message(section),
                }
                for section in generic
            ],
            # 自建件计划（工单 03 落数据、工单 05 起页面渲染它）：库内两批之后那一批
            # ——判据来自**用户确认的事实**、不是库内配方，所以页面与产物的顺序都是
            # "库内验证过的在前"。文案（tag / plan / 三档说明 / 不出小节那句）与
            # 接线那一行全部来自 `hwcheck_custom` 单源，前端一个字不另写。
            "custom": custom_payload,
            # 同组互斥（工单 05）：按**平台**投影的库级功能组——判据单源是库内
            # manifest 的 exclusive_group（`collect_exclusive_groups`，与赛题侧
            # 生成链路同一个函数）；成员取自**整库**而不是本次选中的模块集，
            # 否则"点了同组第二件"时它还不在这份清单里，单选交换就无从下手。
            "exclusive_groups": [
                {"id": group.id, "label": group.label,
                 "members": [member.slug for member in group.members]}
                for group in collect_exclusive_groups(
                    list(by_slug.values()), platform=config.platform
                )
            ],
        },
        sections=sections,
        generic=generic,
        custom=custom_sections,
        custom_plan=custom_plan,
        # 引脚消解出的绑定增量（工单 hwcheck-pin-conflict-exit/01）：生成端点原样
        # 喂生成内核——页面接线表与工程 README / 接线快照因此是同一组脚。
        pin_bindings=plan.bindings,
        # 整库 slug 词表（工单 08）：排障的事实约束要判"模型提到的模块是不是
        # 库内别的件"——`by_slug` 反正已经在这儿了，不必再扫一遍库。
        # 端点各自 `**view.board` 展开，这条**不进载荷**（页面用不上）。
        known_slugs=tuple(by_slug),
        # 生成端点要吃的那个 slug 集（与上面 manifests 同源——页面接线表、main.c、
        # 工程里进哪些模块，三处因此是同一个集合）。
        generation_slugs=tuple(module_slugs),
        # 已被删掉、但仍留在选择集里的自建件（工单 ci-gate-fixes/09）：端点带给页面，
        # 页面如实说一句"已不在你的器件里"（这里摘掉是**装配**动作，不是判据来源）。
        dropped_devices=dropped_custom,
    )
