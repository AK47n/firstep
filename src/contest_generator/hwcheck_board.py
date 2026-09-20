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
的页面用（检测页不读题面、不进生成流程），而它的三块输入分别住在 wiring /
pin_bindings / readme 三个模块里。拼装逻辑留在这里，路由只取参转调；`hwcheck.py`
继续只管"检测程序长什么样"（纯函数、不碰盘），本模块是它的板侧对偶。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from .boards import Board, board_for_platform
from .hwcheck import dedup_slugs, require_known_platform
from .library import list_modules
from .manifest import ModuleManifest
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
from .syscfg_prune import SyscfgPinConflictReport, syscfg_pin_conflict_report
from .wiring import wiring_rows

__all__ = [
    "HWCHECK_ORDER_REASON",
    "HWCHECK_PIN_EXIT_MARKER",
    "HwCheckBoardView",
    "HwCheckPinPlan",
    "hwcheck_board_view",
    "hwcheck_board_view_for",
    "hwcheck_missing_message",
    "hwcheck_pin_message",
    "hwcheck_pin_plan",
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


@dataclass(frozen=True)
class HwCheckPinPlan:
    """检测页的引脚消解结果（工单 hwcheck-pin-conflict-exit/01）。

    `bindings` = 增量（自动让位的角色 → 新脚），原样喂生成内核（工程 README /
    接线快照因此与页面同源）；`resolved` = 校验后的绑定（接线表 / 冲突组按它渲染）；
    `fixed` = 「动了哪几根线」的人话说明行；`conflict` = 装不下时的页面文案
    （空串 = 这一趟能生成）。
    """

    bindings: dict[str, str] = field(default_factory=dict)
    resolved: tuple[ResolvedBinding, ...] = ()
    fixed: tuple[str, ...] = ()
    conflict: str = ""

    @property
    def ok(self) -> bool:
        return not self.conflict


def hwcheck_pin_plan(
    platform: str,
    manifests: Sequence[ModuleManifest],
    board: Board,
    master_syscfg: str | None,
) -> HwCheckPinPlan:
    """检测页生成前的引脚消解（纯函数：吃已解析的 manifest / 板 / 母版 syscfg 文本）。

    两步，判据全部复用既有单源：

    1. **自动解冲突** = `auto_assign_bindings(resolve_default_conflicts=True)`
       ——与赛题页「自动配置」按钮同一个求解器、同一个开关；只动真冲突的角色，
       合法共享（含薄封装共读同槽）不动。
    2. **装不装得下** = `syscfg_prune.syscfg_pin_conflict_report`（落盘文本的同脚
       多实例冲突）——与生成门禁**同一个函数**，所以「预览通过 → 生成 400」这类
       分家不可能再出现；装不下时给出检测页能执行的出路（`hwcheck_pin_message`）。

    **只对 mspm0 自动搬**：stm32 的默认脚重叠按 ADR 0010 是提示语义、不拦生成，
    搬了反而改掉既有工程（逐字节回归），故 stm32 返回空计划。
    `master_syscfg` 缺失（母版没导入 / 假母版）= 判不了就不判，只做第 1 步。
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
        return HwCheckPinPlan(dict(solved.bindings), resolved, solved.fixed)
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
    if not report.lines:
        return HwCheckPinPlan(dict(solved.bindings), resolved, solved.fixed)
    return HwCheckPinPlan(
        dict(solved.bindings),
        resolved,
        solved.fixed,
        hwcheck_pin_message(report, board.name),
    )


def hwcheck_pin_message(report: SyscfgPinConflictReport, board_name: str) -> str:
    """「这套选择装不下」的页面文案（**检测页**出路，不是赛题页那句话）。

    为什么必须单独一句：检测页没有引脚配置入口，生成门禁那句「在引脚配置里改绑
    （或点自动配置）」对学生是不可执行的指令（本单的由来）。所以这里给三条
    检测页做得到的动作，把「去赛题页改绑」降为第三条而不是唯一一条。

    `board_name` 由调用方传（板上就那一块板，`hwcheck_pin_plan` 手里有板对象）
    ——板名是单源事实（`boards/*.json`），不在这句话里另写一份；容量诊断段自己
    也用同一份板名，两处必须同一块板。
    文案里的 `HWCHECK_PIN_EXIT_MARKER` 是判据哨兵（见常量说明）。
    """
    return (
        f"这套选择在「{board_name}」上装不下：落盘后的 mspm0.syscfg 有 "
        f"{report.pin_count} 个引脚被两只实例同时占用，SysConfig 会直接报 "
        "Resource conflict（工程编不过）。自动移脚已经尽力，剩下的靠改绑解不开：\n"
        + "\n".join(report.lines)
        + report.capacity
        + f"\n{HWCHECK_PIN_EXIT_MARKER} 检测页能做到的出路（挑一条）：\n"
        "  1. 回到上面的器件选择，把冲突的那几件去掉——上面【引脚容量】那段"
        "点名了是哪些件、至少要去掉几个；\n"
        "  2. 只勾一个输出通道（「调试串口」或「OLED」）再生成；\n"
        "  3. 两路都要、这几件也都要 → 先到「做题」页的引脚配置里把它们分开，"
        "再回来生成（检测页暂时没有改绑入口）。"
    )


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

    def to_dict(self) -> dict:
        """JSON 载荷形态（preview / generate / project 三个端点共用一处投影）。"""
        return {
            "rows": [dict(row) for row in self.rows],
            "groups": [dict(group) for group in self.groups],
            "board_shares": [dict(item) for item in self.board_shares],
            "order": [dict(item) for item in self.order],
            "missing": [dict(item) for item in self.missing],
            "pin_fixes": list(self.pin_fixes),
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
) -> HwCheckBoardView:
    """投影一次（纯函数：吃已解析的 manifest 集与板定义，不碰盘）。

    `manifests` = 依赖展开后的集合（`resolve_dependencies` 的结果，顺序即进工程
    顺序）——调用方与生成内核吃的是同一个集合，接线行/顺序因此与工程 README 同源。
    `devices` = 用户选中的器件（判"本平台有没有条目"用；不传 = 不报缺，
    框架与通道模块的缺条目属于环境坏，由生成侧大声失败）。
    `resolved_bindings` / `pin_fixes`（工单 hwcheck-pin-conflict-exit/01）=
    `hwcheck_pin_plan` 的消解结果：接线行按**生效脚**渲染、冲突组按生效布局判
    （学生照页面接线，页面的脚必须与工程 README 一致），`pin_fixes` 原样带给页面。
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
        missing=_missing_devices(platform, manifests, devices),
        pin_fixes=_pin_fixes(pin_fixes, resolved_bindings, pins),
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


def _missing_devices(
    platform: str, manifests: Sequence[ModuleManifest], devices: Sequence[str]
) -> tuple[dict, ...]:
    """选中器件里本平台没有条目的那些（判据 = selection 的平台警告表）。

    保序去重（用户点选的顺序，`dedup_slugs` 单源），逐条给中文文案——**点名，
    不静默省略**：悄悄从接线表里消失会让学生以为"选上了、待会儿就能测"。
    """
    wanted = list(dedup_slugs(devices))
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
