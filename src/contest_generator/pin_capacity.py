"""引脚容量诊断（工单 pin-capacity/01）：生成期引脚冲突为何解不开、最低代价多少。

为什么单独立域模块：生成门禁 `syscfg_pin_conflicts` 只回答「哪些脚被两只实例抢了」，
用户拿到的那句 400 没有数字，于是三条都答不上来——这个选中集在这块板上**可不可能**
实现？「自动配置」是解法还是死路？要砍几个模块？本模块就是这三个问题的确定答案。

**为什么叫「引脚容量」**：本仓库的「预算」已被 `budget.py`（LLM 请求体字节预算）占用，
容量/预算类的判定与文案各占一个域模块，命名不得混用（工单命名硬约束）。

判定量**只复用现成两件**（不新造判据，两处各写一遍必漂移）：

- 落点与占用脚 = `pin_bindings._role_entries`（绑定优先、缺省声明默认脚；与
  `_shared_groups` / 默认脚消解相共用同一推导）；
- 可解性 = `auto_assign_bindings(..., resolve_default_conflicts=True)` 的 `shared` 中
  `kind == "conflict"` 的**剩余组**（与生成页「自动配置」按钮同一个求解器、同一个开关）；
- 板上可用 IO = 板定义里 `capabilities` 非空的脚（与求解器的候选脚域同口径）。

口径（用户拍板，见 spec「实现决策」）：

1. **可用 IO = 整板可用脚**，另报「占用 / 剩余空闲」；
2. **以 solver 剩余组为准**：角色落点数只作**上界**背景（合法共享会省脚）；
3. **落点 ≤ 可用脚却仍无解** → 另说「与引脚数量无关，卡在能力/实例分配」。

口径边界（如实记账，也是文案措辞的依据）：落点数按 `_role_entries` 统计，它**含没有
可落脚默认脚的板外角色**（这类角色进不了求解器的候选脚域），所以「落点 > 可用脚」只是
**预警**、不是硬证明。硬证明只能来自求解器：**改绑后仍有剩余组 + 板上可用 IO 脚全被
占用（真空闲 0 脚）** —— 那时「至少要去掉一个模块」是必然的。故渲染把硬事实放在最前，
落点数只作背景。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Sequence

from .boards import Board
from .manifest import ModuleManifest
from .pin_bindings import (
    _group_modules,
    _group_roles,
    _role_entries,
    _shared_groups,
    auto_assign_bindings,
)


@dataclass(frozen=True)
class PinCapacityReport:
    """一次容量诊断的判定结果（渲染只吃本结构，不重复计算）。

    脚口径统一（都按「占用脚集合」的势）：`occupied` / `free` / `free_after_moves`
    三个字段说的都是**脚**；`slots` 是**角色落点数**（上界口径，另行标注）。

    `unresolved_roles` 是**逐组**的角色对（组内角色按 `_shared_groups` 的键序），
    供文案逐地点名；`unresolved_modules` 是这些组里出现过的模块（保序去重）——
    「至少要去掉几个模块」的**下界** = `unresolved_groups`（每个无解组至少去掉一方），
    不是 `len(unresolved_modules)`。
    """

    modules: int  # 选中集（含依赖展开）模块数
    slots: int  # 引脚落点：角色数（上界口径，合法共享会落在同脚）
    board_io: int  # 板上可用 IO 脚（capabilities 非空）
    occupied: int  # 本次占用脚数（解冲突前）
    free: int  # 本次空闲脚数（解冲突前）
    conflict_groups: int  # 门禁发现的同脚冲突组数
    moved_groups: int  # 「自动配置」能解开的冲突**组**数（不是角色数）
    unresolved_groups: int  # 剩余无法靠改绑解开的组数
    unresolved_roles: tuple[tuple[str, ...], ...]  # 剩余组逐个的角色对
    unresolved_modules: tuple[str, ...]  # 剩余组涉及的模块（保序去重）
    free_after_moves: int  # 解冲突后的真空闲脚（0 = 脚已用尽）

    @property
    def solvable(self) -> bool:
        """剩余无解组为 0 = 这个选中集靠改绑就能落地。"""
        return self.unresolved_groups == 0


def diagnose_pin_capacity(
    manifests: Sequence[ModuleManifest],
    platform: str,
    board: Board,
    bindings: Mapping[str, str],
) -> PinCapacityReport:
    """现算一次引脚容量诊断（只读入参，不写任何状态）。

    调用方须已保证 `manifests` 非空、`board` 是本平台的板——空选中集 / 缺板定义
    形态由调用方走缺省文案（那两种形态没有诊断可言，本函数不为它们编数字）。
    """
    io_count = _io_pin_count(board)
    before = _occupied_pins(manifests, platform, bindings)
    solved = auto_assign_bindings(
        manifests, platform, board, bindings, resolve_default_conflicts=True
    )
    after = _occupied_pins(manifests, platform, solved.bindings)

    remaining = [group for group in solved.shared if group["kind"] == "conflict"]
    moved_groups = len(
        [
            group
            for group in _shared_groups(manifests, platform, board, bindings)
            if group["kind"] == "conflict"
        ]
    ) - len(remaining)

    unresolved_roles: list[tuple[str, ...]] = []
    modules: list[str] = []
    for group in remaining:
        unresolved_roles.append(tuple(_group_roles(group)))
        for slug in _group_modules(group):
            if slug not in modules:
                modules.append(slug)

    return PinCapacityReport(
        modules=len(manifests),
        slots=len(_role_entries(manifests, platform, bindings)),
        board_io=io_count,
        occupied=len(before),
        free=max(0, io_count - len(before)),
        conflict_groups=moved_groups + len(remaining),
        moved_groups=moved_groups,
        unresolved_groups=len(remaining),
        unresolved_roles=tuple(unresolved_roles),
        unresolved_modules=tuple(modules),
        free_after_moves=max(0, io_count - len(after)),
    )


def _occupied_pins(
    manifests: Sequence[ModuleManifest],
    platform: str,
    bindings: Mapping[str, str],
) -> set[str]:
    """当前落点占用的**不同脚**集合（`occupied` / `free` / `free_after_moves` 的同一口径）。"""
    return {
        pin for _key, _slug, _decl, pin in _role_entries(manifests, platform, bindings)
    }


def _io_pin_count(board: Board) -> int:
    """板上可用 IO 脚数（`capabilities` 非空）——与求解器候选脚域同口径，只此一处判据。"""
    return sum(1 for pin in board.pins if pin.capabilities)


def _headline(report: PinCapacityReport, board_name: str) -> str:
    """容量头一行（两种形态共用）：规模 / 上界落点 / 板上容量 / 占用与空闲。"""
    return (
        f"【引脚容量】{report.modules} 个模块 / {report.slots} 个引脚落点"
        f"（上界：合法共享会少占脚）；{board_name} 板载可用 IO {report.board_io} 脚，"
        f"本次已占 {report.occupied} 脚、剩余 {report.free} 脚。"
    )


def render_pin_capacity_diagnosis(report: PinCapacityReport, board_name: str) -> str:
    """判定结果 → 门禁 400 文案里的可操作数字段（纯渲染，不重算）。

    `board_name` 由调用方传（门禁手上就有板对象）——板名是给人读的，判定不吃它。
    """
    lines = [_headline(report, board_name)]
    if report.solvable:
        lines.append(
            f"实测到的 {report.conflict_groups} 组同脚冲突"
            f"「自动配置」都可以解开（会解开 {report.moved_groups} 组），"
            f"改绑后剩余空闲 {report.free_after_moves} 脚——不必去掉模块。"
        )
        return "\n".join(lines)

    lines.append(
        f"实测到的 {report.conflict_groups} 组同脚冲突"
        f"「自动配置」可解开 {report.moved_groups} 组，"
        f"剩余 {report.unresolved_groups} 组无法靠改绑解开（任一方模块让位即可）："
    )
    for roles in report.unresolved_roles:
        lines.append("    · " + " × ".join(roles))
    module_text = "、".join(report.unresolved_modules)
    if report.free_after_moves > 0:
        lines.append(
            f"这些冲突与引脚数量无关（当前选中集的引脚落点 {report.slots} ≤ 板载可用 IO "
            f"{report.board_io} 脚），卡在引脚能力 / 外设实例分配上——请改绑上述角色，"
            f"或去掉或替换冲突模块（{module_text}）。"
        )
    elif report.slots > report.board_io:
        # 注意措辞纪律：落点数含板外角色，只是**上界**——故它排在硬事实之后作佐证，
        # 不单独承担「不可实现」的结论（硬事实 = 改绑后仍有剩余组 + 一行空脚都不剩）。
        lines.append(
            f"解冲突后板上的可用 IO 脚已全被占用（{report.board_io} 脚，一个空闲脚都不剩），"
            f"而剩余冲突组无法靠改绑解开——该选中集在{board_name}上物理不可实现："
            f"至少要去掉 {report.unresolved_groups} 个模块（冲突模块：{module_text}）。"
            f"（佐证：引脚落点 {report.slots} 个 > 板上可用 IO {report.board_io} 脚；"
            f"落点含合法共享与没有可落脚默认脚的角色，只是上界。）"
        )
    else:
        lines.append(
            f"解冲突后板上的可用 IO 脚已全被占用（{report.board_io} 脚，一个空闲脚都不剩），"
            f"而剩余冲突组无法靠改绑解开——该选中集在{board_name}上无法落地："
            f"至少要去掉 {report.unresolved_groups} 个模块（冲突模块：{module_text}）。"
        )
    return "\n".join(lines)
