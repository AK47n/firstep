"""mspm0 syscfg 文本级判据（工单 syscfg-prune/01 + hwcheck-pin-conflict-exit/01）。

三件东西，都是「按选中集处理母版 mspm0.syscfg」这件事的一部分：

1. **裁剪**（`prune_syscfg` / `SyscfgModel.prune`）：母版 = 全量实例（默认布局
   理论上限）。生成时按本次选中的模块集裁剪：未选模块的实例不落盘，其引脚空出来
   可绑——bindings 写到这些脚不再撞 SysConfig Resource conflict。实例 → 消费模块
   映射单源表在 syscfg_instances.py。
2. **槽位级裁剪的判据**（`AdcSlotPlan` / `adc_slot_plan`，工单
   hwcheck-pin-conflict-exit/01）：ADC12_0 这类**一个实例服务十几个模块**的件，
   实例粒度裁剪不够——没选中的模块的那几根 ADC 脚照样落盘，冲突求解器看不见它们
   （角色「未登记」），于是检测页在 mspm0 上必 400。本函数装配两个入参喂
   `SyscfgModel.prune`：`claims`（本趟声明了哪些 MEM 槽位）与 `occupied`
   （本趟所有已声明角色的生效脚，含绑定——单源复用 `pin_bindings._role_entries`，
   与冲突求解器的「空闲脚」口径必须同一份）。
3. **落盘文本的同脚冲突报告**（`syscfg_pin_conflict_report`）：判据 = 写侧将要
   落盘的那份 syscfg（母版 → prune(选中集) → rewrite(绑定)，与
   `pinwriter.apply_pin_bindings` 同一条 pipeline）里同一个引脚被**两只实例**
   占用 = SysConfig 的 Resource conflict。**门禁与检测页共用本函数**：生成门禁
   据此抛 `SyscfgPinConflictError`（赛题页出路），检测页据此抛 `HwCheckError`
   （检测页出路）——判据一处，出路两句（两页能做的事不同）。

裁剪文法收敛到 syscfg_model（工单 syscfg-file-model/02）：本模块不持实例/模块
声明正则；文件级裁剪挂钩并入 pinwriter.apply_pin_bindings 的单一 pipeline
（工单 syscfg-file-model/04），本模块也不为文件名反向 import pinwriter。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .boards import Board
from .manifest import ModuleManifest
from .pin_bindings import _role_entries, resolve_bindings
from .pin_capacity import diagnose_pin_capacity, render_pin_capacity_diagnosis
from .platforms import PLATFORM_MSPM0
from .syscfg_instances import INSTANCES_BY_SLUG
from .syscfg_model import (
    AdcSlotPlan,
    SyscfgModel,
    adc_mem_index,
    parse_syscfg,
    syscfg_path_matches,
)

__all__ = [
    "AdcSlotPlan",
    "SyscfgPinConflictReport",
    "adc_slot_plan",
    "prune_syscfg",
    "syscfg_pin_conflict_report",
]


def adc_slot_plan(
    manifests: Sequence[ModuleManifest],
    platform: str,
    bindings: Mapping[str, str] | None = None,
) -> AdcSlotPlan:
    """装配 `AdcSlotPlan`（纯函数，不读盘）。

    - `claims` 从 manifest 的 adc 类型角色来（id 尾 `_CH<N>` = MEM 槽位号；
      角色 → 消费 syscfg 实例走 `INSTANCES_BY_SLUG` 单源表）；
    - `occupied` 复用 `pin_bindings._role_entries`——**必须**与冲突求解器
      「哪些脚已被占」同一推导，否则门禁预测的落盘文本与写侧真实落盘会分家
      （门禁看不见被绑到孤儿脚上的角色 = 编译期才发现）。
    """
    claims: dict[str, set[int]] = {}
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for decl in entry.pins:
            if decl.type != "adc":
                continue
            mem = adc_mem_index(decl.id)
            for instance in INSTANCES_BY_SLUG.get(manifest.slug, ()):
                claims.setdefault(instance, set()).add(mem)
    occupied = frozenset(
        pin
        for _key, _slug, _decl, pin in _role_entries(
            manifests, platform, bindings or {}
        )
    )
    return AdcSlotPlan(
        claims={name: frozenset(slots) for name, slots in claims.items()},
        occupied=occupied,
    )


def prune_syscfg(
    master_text: str,
    selected_slugs: Iterable[str],
    *,
    plan: AdcSlotPlan | None = None,
) -> str:
    """按选中模块裁剪 mspm0.syscfg 全文。

    规则：实例的消费模块集与 selected_slugs 交集为空 → 裁掉该实例的
    `const X = MOD.addInstance();` 行与所有 `X.` 配置行；某模块变量
    （UART/I2C/TIMER/GPIO/PWM）的全部实例被裁 → 连 `const MOD =
    scripting.addModule(...)` 行一起裁。Board/SYSCTL 与文件头注释不动。

    `plan`（可选）= 槽位级裁剪判据（`adc_slot_plan`）：给了就让没被本趟声明、
    又撞上已声明角色的 ADC 孤儿槽位让位（见 `SyscfgModel.prune`）；不给 =
    整实例粒度，与迁移前逐字节一致。委托给文件模型 `SyscfgModel.prune`
    （工单 syscfg-file-model/02 起），文法与裁剪逻辑单源。
    """
    return (
        parse_syscfg(master_text).prune(selected_slugs, adc_plan=plan).to_text()
    )


@dataclass(frozen=True)
class SyscfgPinConflictReport:
    """落盘 syscfg 的同脚冲突报告。

    `lines` = 逐脚一行「  · PA22：角色 × 角色」（空 = 无冲突）；
    `capacity` = 引脚容量诊断段（前面带换行；两种形态没有诊断可言 = 空串：
    ① 无选中集知识（产物复核）② 板数据缺失）。
    """

    lines: tuple[str, ...]
    capacity: str

    @property
    def pin_count(self) -> int:
        """冲突引脚数（调用方文案里的「N 个引脚」）。"""
        return len(self.lines)


def syscfg_pin_conflict_report(
    *,
    master_syscfg: str | None,
    manifests: Sequence[ModuleManifest],
    platform: str,
    board: Board | None,
    bindings: Mapping[str, str] | None,
    diagnosis_bindings: Mapping[str, str] | None = None,
) -> SyscfgPinConflictReport:
    """落盘 syscfg（prune + rewrite 后）的同脚多实例冲突报告（判据单源）。

    非 mspm0（stm32 的默认脚重叠按 ADR 0010 是提示语义、不拦生成）与语料无
    syscfg（假母版 / 测试树）→ 空报告，直接返回。

    `bindings` = **将要落盘的**绑定（判据本体：门禁吃用户的原始载荷，检测页吃
    自动解冲突后的增量）；`diagnosis_bindings` = 引脚容量诊断的基准绑定，缺省 =
    `bindings`。两者要分开的一处真实场景：检测页自动解冲突之后再问「这组选择
    本来能不能解开」，若拿已经搬过的增量当基准，那些被搬过的角色会被诊断当成
    「用户显式绑定」（不可再让位），于是报出「可解开 0 组」这种与事实相反的读数
    ——本单实测撞到过。

    产物复核形态（`build_output_tree_corpus` + `run_generation_gates(corpus, [],
    platform)`）没有选中集知识：语料里的 syscfg 已是生成时落盘的结果，**不再
    prune / 不再 rewrite**，直接判现值——空 manifests 下若仍 prune 会把实例
    全裁掉、判据静默失明。
    """
    if platform != PLATFORM_MSPM0 or not master_syscfg:
        return SyscfgPinConflictReport(lines=(), capacity="")
    origin = parse_syscfg(master_syscfg)
    if manifests:
        plan = adc_slot_plan(manifests, platform, bindings)
        pruned = origin.prune(
            (manifest.slug for manifest in manifests), adc_plan=plan
        )
        resolved = (
            resolve_bindings(manifests, platform, board, bindings)
            if bindings and board is not None
            else ()
        )
        model = pruned.rewrite(resolved)
        # 角色标签取「裁剪后、改写前」的那份：GPIO 组角色的 `$assign` 路径
        # （<实例>.associatedPins[n].pin）只带实例名，一个实例下多条落点要按
        # 「现脚 == 声明默认脚」消歧——改写后现脚已变，消歧就失效了；而改写
        # 只改引号里的值、路径不变，故按路径回查仍成立。
        roles = _syscfg_role_labels(pruned, manifests, platform)
    else:
        # 产物复核形态：语料即生成时落盘结果，不裁剪不改写
        model = origin
        roles = {}
    by_pin: dict[str, list[str]] = {}
    for assign in model.assigns:
        by_pin.setdefault(assign.pin, []).append(assign.path)
    conflicts = {
        pin: paths
        for pin, paths in by_pin.items()
        if len({path.split(".", 1)[0] for path in paths}) > 1
    }
    if not conflicts:
        return SyscfgPinConflictReport(lines=(), capacity="")
    lines = [
        "  · " + pin + "：" + " × ".join(
            roles.get(path, f"{path}（角色未登记）") for path in conflicts[pin]
        )
        for pin in sorted(conflicts)
    ]
    # 引脚容量诊断（工单 pin-capacity/01）：只升文案、不增拦截——判据与触发条件
    # 一行未改，只在逐脚清单之后、出路之前补可操作数字（选中集规模 / 板上可用 IO /
    # 占用与空闲 / 一键配置解开几组剩几组 / 最低代价几个模块）。两种形态没有诊断
    # 可言，走缺省文案：① 无选中集知识（产物复核，manifests 为空）；② 板数据缺失
    # ——都给不出「可用 IO / 落点」这些数，编不得。
    capacity = ""
    if manifests and board is not None:
        capacity = "\n" + render_pin_capacity_diagnosis(
            diagnose_pin_capacity(
                manifests,
                platform,
                board,
                bindings if diagnosis_bindings is None else diagnosis_bindings,
            ),
            board.name,
        )
    return SyscfgPinConflictReport(lines=tuple(lines), capacity=capacity)


def _syscfg_role_labels(
    model: SyscfgModel, manifests: Sequence[ModuleManifest], platform: str
) -> dict[str, str]:
    """`$assign` 路径 → 「模块（路径，角色 <slug>.<id>）」人话标签。

    角色反查 = `syscfg_path_matches`（槽位身份原语，校验侧 / 写侧共用）；GPIO 组
    一个实例下有多条落点（DC_MOTOR 十个脚）时，用「现脚 = 该角色声明默认脚」消歧
    ——母版默认布局下这个等式恒成立（传入的必须是**未改写**的模型）。消歧不出唯一
    角色（改写过 / 母版漂移）= 只报路径，不猜角色。
    """
    labels: dict[str, str] = {}
    for assign in model.assigns:
        candidates = [
            (manifest.slug, decl)
            for manifest in manifests
            if manifest.platforms.get(platform) is not None
            for decl in manifest.platforms[platform].pins
            if syscfg_path_matches(decl.type, decl.id, manifest.slug, assign.path)
        ]
        for slug, decl in candidates:
            if decl.default == assign.pin:
                labels[assign.path] = f"{slug}（{assign.path}，角色 {slug}.{decl.id}）"
                break
        else:
            labels.setdefault(assign.path, f"{assign.path}（角色未登记）")
    return labels
