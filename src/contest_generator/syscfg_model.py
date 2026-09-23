"""mspm0.syscfg 文件模型（架构评审 ② 落地）：独占文法 + 一次解析 + 槽位身份。

母版 mspm0.syscfg 的「文件格式知识」曾散在三处：syscfg_prune 拥有实例声明
文法、pinwriter 拥有 `$assign` 文法与路径匹配、槽位身份在 pin_bindings 又
实现了一遍。本模块把它们收敛成单一文件模型：

- `parse_syscfg` 独占几份文法（实例声明 addInstance / `$assign` 赋值 / 关联引脚
  符号 `associatedPins[n].$name`；模块声明 addModule 的匹配归 `prune`），一次
  解析为 `SyscfgModel`；
- `SyscfgModel.prune` / `SyscfgModel.rewrite` 是对同一解析的两个操作，各自
  产出新的模型，`SyscfgModel.to_text` 是唯一回写出口（先后由调用方 pipeline
  构造保证，不再靠注释）；
- `syscfg_path_matches` 是槽位身份原语（binding → syscfg 实例/路径），校验
  侧与写侧共用。

逐字节契约：parse + prune + rewrite 输出与旧 prune→rewrite 顺序逐字节一致
（test_syscfg_model 断言）。文本进 / 文本出的纯函数接缝；母版 syscfg 是
CRLF，读/写走 newline="" 原样保留行尾。工单 02/03/04 已把 syscfg_prune 裁剪
/ pinwriter 改写切到本模型、删旧文法——本模块现为 syscfg 文件格式知识与
写侧唯一实现（pinwriter.apply_pin_bindings 的 mspm0 单一 pipeline 也在此）。

实例 ↔ 消费模块映射单源表仍在 syscfg_instances.py（那是数据，不是文法，本
模块只消费 INSTANCE_CONSUMERS / INSTANCES_BY_SLUG）。
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .syscfg_instances import INSTANCE_CONSUMERS, INSTANCES_BY_SLUG

if TYPE_CHECKING:
    from .pin_bindings import ResolvedBinding

__all__ = [
    "MSPM0_SYSCFG_FILENAME",
    "AdcSlotPlan",
    "SyscfgAssign",
    "SyscfgInstance",
    "SyscfgModel",
    "SyscfgModelError",
    "adc_mem_index",
    "parse_syscfg",
    "syscfg_path_matches",
]

MSPM0_SYSCFG_FILENAME = "mspm0.syscfg"

# 实例声明：`const PWMAB = PWM.addInstance();`（行尾可带分号/CRLF）。
_INSTANCE_DECL_RE = re.compile(
    r"^\s*const\s+(?P<instance>[A-Za-z_]\w*)\s*=\s*(?P<module>[A-Za-z_]\w*)"
    r"\.addInstance\(\);?\s*(?P<eol>\r?\n)?$"
)
# 模块声明：`const PWM = scripting.addModule(...);`
_MODULE_DECL_RE = re.compile(
    r"^\s*const\s+(?P<module>[A-Za-z_]\w*)\s*=\s*scripting\.addModule\(.*$"
)
# `$assign` 赋值：<路径>.$assign = "<值>"——path 捕获实例路径（引脚落点
# peripheral/ccp0Pin/rxPin/txPin/sdaPin/sclPin/pin 全形态与 peripheral 外设行
# 共用此形态），值 = 引脚名或外设名（peripheral 行的 UART0/TIMG0 等）；
# head/tail/eol 单独捕获（CRLF 母版，rewrite 重构时行尾原样接回）。
_SYSCFG_ASSIGN_RE = re.compile(
    r'^(?P<head>\s*(?P<path>.+?)\.\$assign\s*=\s*)"(?P<pin>[A-Za-z0-9]+)"'
    r"(?P<tail>.*?)(?P<eol>\r?\n)?$"
)
# 关联引脚的**符号名**：`<实例>.associatedPins[n].$name = "SCL"`（工单 11）。
# 与 `$assign` 分开一条：`$name` 的值是**符号**（SysConfig 里全局唯一），
# `$assign` 的值是**引脚**（同一个脚只许一只实例占）——两根轴的判据不同。
_SYSCFG_PIN_NAME_RE = re.compile(
    r'^\s*(?P<instance>[A-Za-z_]\w*)\.associatedPins\[\d+\]\.\$name\s*=\s*'
    r'"(?P<name>[^"]*)"\s*;?\s*(?:\r?\n)?$'
)

# 需要连带改写 peripheral 行的角色类型（工单 pin-full-unlock/03）：
# uart/i2c/pwm 的引脚落点路径尾字段 → 实例行路径（去掉尾字段）。
_MSPM0_PERIPHERAL_TYPES = ("uart_tx", "uart_rx", "i2c_scl", "i2c_sda", "pwm")
_PERIPHERAL_PIN_FIELDS = ("txPin", "rxPin", "sdaPin", "sclPin", "ccp0Pin", "ccp1Pin")

# ADC12 通道行：`<实例>.adcMem<N>chansel = "DL_ADC12_INPUT_CHAN_<M>"`——普通赋值
# 行（非 $assign），绑定换引脚时随 adcPin 落点一起改写（b1-adc-servo/01）。
_ADC_MEM_RE = re.compile(
    r'^(?P<head>\s*(?P<path>[A-Za-z_]\w*\.adcMem\dchansel)\s*=\s*)'
    r'"(?P<value>[^"]+)"(?P<tail>.*?)(?P<eol>\r?\n)?$'
)

# ADC 能力实例 token → 通道号：A0_3 → 3（DL_ADC12_INPUT_CHAN_3，TI 命名
# A0_<N> 与 CHAN_<N> 对应）；A1_* 组 v1 不支持（返回 None 大声失败）。
_ADC_CHAN_RE = re.compile(r"A0_(\d+)\Z")

# `adcMem<N>chansel` 的槽位号与通道号（孤儿槽位让位用，工单
# hwcheck-pin-conflict-exit/01：`adcMem6chansel = "DL_ADC12_INPUT_CHAN_7"` →
# 槽位 6 / 通道 7）。
_ADC_MEM_SLOT_RE = re.compile(r"\.adcMem(?P<mem>\d+)chansel\Z")
_ADC_CHAN_VALUE_RE = re.compile(r"DL_ADC12_INPUT_CHAN_(?P<chan>\d+)\Z")

# ADC 引脚落点行：`<实例>.peripheral.adcPin<通道>.$assign = "<脚>"`——孤儿槽位
# 让位时整行改成注释（见 `_relocate_unclaimed_adc_slots`）。
_ADC_PIN_ASSIGN_RE = re.compile(
    r'^(?P<head>\s*)(?P<inst>[A-Za-z_]\w*)\.peripheral\.adcPin(?P<chan>\d+)'
    r'\.\$assign\s*=\s*"(?P<pin>[A-Za-z0-9]+)"(?P<tail>.*?)(?P<eol>\r?\n)?$'
)


class SyscfgModelError(ValueError):
    """syscfg 文件模型操作失败（母版漂移 / 数据漂移等防御路径）。

    迁移期（工单 03）由 pinwriter 翻译回 PinBindingError 保持旧错误契约；
    消息文案与旧实现逐字一致。
    """


@dataclass(frozen=True)
class SyscfgInstance:
    """一条实例声明的解析产物：`const <name> = <module>.addInstance();`。"""

    name: str
    module: str
    line: int


@dataclass(frozen=True)
class SyscfgAssign:
    """一条 `$assign` 落点的解析产物：`<path>.$assign = "<pin>"`。"""

    path: str
    pin: str
    line: int


@dataclass(frozen=True)
class AdcSlotPlan:
    """槽位级裁剪的判据（工单 hwcheck-pin-conflict-exit/01）：`prune` 的输入形状。

    两个字段成对使用、成对传（装配在 `syscfg_prune.adc_slot_plan`，门禁与写侧传
    同一份），所以合成一个类型而不是两个裸参数——两处各拆一次包迟早分家。

    `claims` = 实例名 → 本趟声明的 ADC MEM 槽位号（role id 尾 `_CH<N>`）；
    `occupied` = 本趟所有已声明角色的**生效脚**（默认脚 ∪ 绑定值）。
    """

    claims: Mapping[str, Collection[int]] = field(default_factory=dict)
    occupied: Collection[str] = ()


@dataclass
class SyscfgModel:
    """mspm0.syscfg 的一次解析产物。

    prune 与 rewrite 是对同一解析的两个操作（产出新的 SyscfgModel；rewrite
    无生效绑定时返回原模型），to_text 是唯一回写出口——先后关系由调用方
    pipeline 构造保证。

    `adc_followers`（工单 hwcheck-pin-conflict-exit/01）= **prune 记下的跟随表**：
    已声明槽位的 `adcMem<N>chansel` 路径 → 跟着它共读同一 ADC 通道的孤儿槽位路径。
    为什么必须记：孤儿槽位让位后没有自己的 `$assign` 行（它的脚靠「与已声明槽位
    同通道」定位），一旦那次生成又给已声明槽位改绑了通道，孤儿槽位不跟着改就会
    指回一个没有显式落点的通道——那属于 SysConfig 隐式分配，静态门禁看不见。
    `parse_syscfg` 恒给空表（跟随关系只在 prune 里产生）。
    """

    lines: list[str]
    instances: dict[str, SyscfgInstance]  # 实例名 -> 实例声明
    assigns: list[SyscfgAssign]  # 全部 $assign 落点（行序）
    adc_followers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # 实例名 -> 关联引脚**符号名**（`associatedPins[n].$name` 的值，行序）。
    # 为什么单独收一栏（工单 11）：`$name` 是 SysConfig 的**全局唯一**约束，
    # 与 `$assign`（同一个脚被两只实例占用）是**两根轴**——只判 `$assign` 会让
    # 「OLED_SPI 与 JY61P 都叫 SCL」这种产物一路生成到编译期才报
    # `Duplicate name`。prune 之后重新 `parse_syscfg` 即天然只留活着的实例，
    # 所以这一栏不需要额外的裁剪逻辑（判据看的就是落盘那一份）。
    pin_names: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def to_text(self) -> str:
        """serialize：行列表拼回全文（splitlines keepends 无损往返）。"""
        return "".join(self.lines)

    def prune(
        self,
        selected_slugs: Iterable[str],
        *,
        adc_plan: AdcSlotPlan | None = None,
    ) -> "SyscfgModel":
        """按选中模块裁剪（对同一解析的 prune 操作，与旧 syscfg_prune 逐字节
        等价）：实例的消费模块集与 selected_slugs 交集为空 → 裁掉该实例的
        `const X = MOD.addInstance();` 行与所有 `X.` 配置行；某模块变量
        （UART/I2C/TIMER/GPIO/PWM）的全部实例被裁 → 连 addModule 行一起裁。
        Board/SYSCTL 与文件头注释不动。产出新的 SyscfgModel。

        `adc_plan`（工单 hwcheck-pin-conflict-exit/01）= **槽位级裁剪**的可选判据
        （`AdcSlotPlan`，装配在 `syscfg_prune.adc_slot_plan`——门禁与写侧传同一份）：
        给了就让**没被本趟声明、又撞上已声明角色生效脚的 ADC 槽位**让位（改成与
        已声明槽位共读同一通道，撤掉它的 `adcPinN.$assign` 行）；没给 = 整实例
        粒度，逐字节等于旧行为。
        """
        selected = set(selected_slugs)
        module_instances: dict[str, list[str]] = {}
        for name, instance in self.instances.items():
            module_instances.setdefault(instance.module, []).append(name)

        pruned_instances = {
            instance
            for instance, consumers in INSTANCE_CONSUMERS.items()
            if not (set(consumers) & selected)
        }
        # 防御：映射表里没登记的实例（母版新增实例忘记更新映射）默认保留——
        # 宁多勿裁，误裁会让选中模块编译炸。
        for instances in module_instances.values():
            for name in instances:
                if name not in INSTANCE_CONSUMERS:
                    pruned_instances.discard(name)

        pruned_modules = {
            module
            for module, instances in module_instances.items()
            if instances and all(i in pruned_instances for i in instances)
        }

        kept: list[str] = []
        for line in self.lines:
            stripped = line.lstrip()
            inst_decl = _INSTANCE_DECL_RE.match(line)
            if inst_decl and inst_decl.group("instance") in pruned_instances:
                continue
            mod_decl = _MODULE_DECL_RE.match(line)
            if mod_decl and mod_decl.group("module") in pruned_modules:
                continue
            if stripped:
                first_token = stripped.split()[0]
                if any(
                    first_token.startswith(instance + ".")
                    for instance in pruned_instances
                ):
                    # `INSTANCE.xxx` 配置行（含 `INSTANCE.associatedPins[n].pin`）
                    continue
            kept.append(line)
        followers: dict[str, tuple[str, ...]] = {}
        if adc_plan is not None:
            followers = _relocate_unclaimed_adc_slots(
                kept, self.instances, adc_plan
            )
        model = parse_syscfg("".join(kept))
        model.adc_followers = followers
        return model

    def rewrite(
        self, resolved: Sequence["ResolvedBinding"]
    ) -> "SyscfgModel":
        """按绑定改写（对同一解析的 rewrite 操作，与旧 pinwriter.rewrite_syscfg
        逐字节等价）：按角色默认引脚值定位 $assign 落点行、换引号里的引脚值；
        uart/i2c/pwm 角色另按同一实例路径改写 `peripheral` 行值。实例名 / 宏名
        / 通道名 / 其余行逐字节不动。产出新的 SyscfgModel；无生效绑定（全部
        = 默认值）返回原模型（与旧 rewrite_syscfg 空改返回原文一致）。"""
        changes: list["ResolvedBinding"] = [
            b for b in resolved if b.pin != b.declaration.default
        ]
        if not changes:
            return self

        lines = list(self.lines)
        sites: dict[str, list[int]] = {}
        path_index: dict[str, int] = {}
        for assign in self.assigns:
            sites.setdefault(assign.pin, []).append(assign.line)
            path_index.setdefault(assign.path, assign.line)

        by_slot: dict[tuple[str, str], str] = {}
        for binding in changes:
            default = binding.declaration.default
            line_no = _locate_mspm0_site(
                lines, sites.get(default) or [], default, binding
            )
            m = _SYSCFG_ASSIGN_RE.match(lines[line_no])
            assert m is not None  # _locate_mspm0_site 已匹配过
            slot = (default, m.group("path"))
            previous_pin = by_slot.get(slot)
            if previous_pin is not None and previous_pin != binding.pin:
                raise SyscfgModelError(
                    f"绑定冲突：同一槽位（默认引脚 {default}，路径"
                    f" {m.group('path')}）的两个角色绑到不同引脚 {previous_pin}、"
                    f"{binding.pin} —— 请绑到同一引脚"
                )
            by_slot[slot] = binding.pin
            # adc 换通道 = 换槽位名（adcPin<N> 的 N = 通道号，b1-adc-servo/01）：
            # 绑定到别的通道脚时 $assign 行路径 adcPin3 → adcPin<新通道>，否则
            # SysConfig 按槽位路由旧通道引脚、新脚无法路由（真机红证 bound/mspm0）
            head = m.group("head")
            if binding.declaration.type == "adc":
                head = _adc_slot_head(head, binding)
            lines[line_no] = (
                f'{head}"{binding.pin}"'
                f'{m.group("tail")}{m.group("eol") or ""}'
            )
            if binding.declaration.type not in _MSPM0_PERIPHERAL_TYPES:
                if binding.declaration.type == "adc":
                    _rewrite_adc_mem_line(lines, binding)
                    _follow_adc_mem_line(lines, binding, self.adc_followers)
                continue
            peripheral_path = _peripheral_path(m.group("path"))
            if peripheral_path is None:
                raise SyscfgModelError(
                    f"角色 {binding.role_key} 的 $assign 路径 {m.group('path')!r}"
                    f" 不是外设引脚字段（txPin/rxPin/sdaPin/sclPin/ccp0Pin/"
                    f"ccp1Pin），无法定位 peripheral 行——母版漂移，请核对"
                )
            peripheral_line_no = path_index.get(peripheral_path)
            if peripheral_line_no is None:
                raise SyscfgModelError(
                    f"角色 {binding.role_key} 的外设实例行"
                    f" {peripheral_path}.$assign 不在母版"
                    f" {MSPM0_SYSCFG_FILENAME} 中——母版漂移，请核对"
                )
            pm = _SYSCFG_ASSIGN_RE.match(lines[peripheral_line_no])
            assert pm is not None  # path_index 收录时已匹配过
            current_peripheral = pm.group("pin")
            instance = _mspm0_instance_for_binding(
                binding.role_key, binding.instances, current_peripheral
            )
            new_peripheral = _mspm0_peripheral_of(instance)
            if new_peripheral != current_peripheral:
                lines[peripheral_line_no] = (
                    f'{pm.group("head")}"{new_peripheral}"'
                    f'{pm.group("tail")}{pm.group("eol") or ""}'
                )
        return parse_syscfg("".join(lines))


def _adc_mem_channel(line: str) -> int | None:
    """`adcMem<N>chansel` 行的通道号（非该形态 / 值不是 CHAN_<N> = None）。"""
    match = _ADC_MEM_RE.match(line)
    if match is None:
        return None
    chan = _ADC_CHAN_VALUE_RE.match(match.group("value"))
    return int(chan.group("chan")) if chan else None


def _relocate_unclaimed_adc_slots(
    lines: list[str],
    instances: Mapping[str, SyscfgInstance],
    plan: AdcSlotPlan,
) -> dict[str, tuple[str, ...]]:
    """ADC 孤儿槽位让位（工单 hwcheck-pin-conflict-exit/01）：原地改 `lines`，返回跟随表。

    **为什么需要**：母版 ADC12_0 把 8 个 MEM 脚全占了，而按选中集裁剪只到**实例**
    粒度——没选中的模块（flame / soil / mq135 …）的那几根脚照样落盘（摘编自母版
    注释的布局），冲突求解器看不见它们（它们不属于任何选中模块，角色「未登记」），
    于是检测页在 mspm0 上必 400。

    **为什么不是「把那几行删掉」**：真机 SysConfig CLI 实证
    （`.scratch/hwcheck-pin-conflict-exit/recon-syscfg-lab.txt`）——只删
    `ADC12_0.peripheral.adcPin7.$assign` 行，SysConfig 会按
    `adcMem6chansel = CHAN_7` 把 PA22 **认回来**、照样报 Resource conflict。
    能过的形态是：把槽位的 chansel 改成与已声明槽位**共读同一通道**，再撤掉它的
    `adcPinN.$assign` 行（「薄封装共读同槽」的既有先例，多 MEM 读同一通道无害）。

    **只动真撞上的**（少动是硬要求）：孤儿槽位占的脚不在 `plan.occupied` 里就保持
    原样——`adc` 配方的第二路读数（MEM1 = PA26）因此仍是 PA26。**没撞上的孤儿脚
    留着不会再挡住生成**：任何一次真撞上都会让它让位。

    返回「跟随表」：已声明槽位（让位目标的取法 = 声明槽位里 MEM 索引最小者）的
    `adcMem<N>chansel` 路径 → 跟着它共读同一通道的孤儿槽位路径元组。
    """
    occupied = set(plan.occupied)
    followers: dict[str, list[str]] = {}
    for name, instance in instances.items():
        if not instance.module.startswith("ADC12"):
            continue
        # 槽位 与 引脚落点：先全量收集，再原地改（不删行——行号即索引）
        slots: dict[int, tuple[int, int, str]] = {}  # mem -> (行号, 通道, 路径)
        pins: dict[int, tuple[int, str, str, str]] = {}  # 通道 -> (行号, 脚, 行尾, 缩进)
        for index, line in enumerate(lines):
            mem_match = _ADC_MEM_RE.match(line)
            if mem_match is not None:
                path = mem_match.group("path")
                if path.split(".", 1)[0] != name:
                    continue
                slot = _ADC_MEM_SLOT_RE.search(path)
                channel = _adc_mem_channel(line)
                if slot is None or channel is None:
                    continue
                slots[int(slot.group("mem"))] = (index, channel, path)
                continue
            pin_match = _ADC_PIN_ASSIGN_RE.match(line)
            if pin_match is not None and pin_match.group("inst") == name:
                pins[int(pin_match.group("chan"))] = (
                    index, pin_match.group("pin"), pin_match.group("eol") or "\n",
                    pin_match.group("head"),
                )
        claimed = sorted(mem for mem in plan.claims.get(name, ()) if mem in slots)
        if not claimed:
            continue  # 判不了就不判：母版漂移 / 本趟没有任何 ADC 声明
        leader_path = slots[claimed[0]][2]
        leader_channel = slots[claimed[0]][1]
        claimed_channels = {slots[mem][1] for mem in claimed}
        for mem in sorted(slots):
            if mem in claimed:
                continue
            line_no, channel, path = slots[mem]
            if channel in claimed_channels:
                # 已经与某个已声明槽位共用同一通道（同一行落点，撤不得）：
                # 记为跟随者即可——那次生成若给已声明槽位改绑，它跟着换。
                if channel == leader_channel:
                    followers.setdefault(leader_path, []).append(path)
                continue
            pin = pins.get(channel)
            if pin is None:
                continue  # 该通道没有显式落点行 = 判不了它占不占脚，保守不动
            pin_line, pin_name, pin_eol, pin_indent = pin
            if pin_name not in occupied:
                continue  # 没撞上任何人 → 保持原样（少动是硬要求）
            # 让位：撤掉落点行（改注释，不删行——行号是后续改写的索引；行尾原样
            # 保留：母版是 CRLF，混一行 LF 会让"逐字节契约"名存实亡）
            lines[pin_line] = (
                f"{pin_indent}// {name}.peripheral.adcPin{channel} 未让位前 = "
                f"\"{pin_name}\"（本趟没有模块声明这个 ADC 槽位，槽位与已声明"
                f"槽位共读同一通道）{pin_eol}"
            )
            lines[line_no] = _with_adc_channel(lines[line_no], leader_channel)
            followers.setdefault(leader_path, []).append(path)
    return {path: tuple(items) for path, items in followers.items()}


def _with_adc_channel(line: str, channel: int) -> str:
    """`adcMem<N>chansel` 行的通道值换成 `channel`（其余逐字节保留）。"""
    match = _ADC_MEM_RE.match(line)
    assert match is not None  # 调用方已匹配过
    return (
        f'{match.group("head")}"DL_ADC12_INPUT_CHAN_{channel}"'
        f'{match.group("tail")}{match.group("eol") or ""}'
    )


def _follow_adc_mem_line(
    lines: list[str],
    binding: "ResolvedBinding",
    followers: Mapping[str, Sequence[str]],
) -> None:
    """让位过的孤儿槽位跟着已声明槽位换通道（prune 记的跟随表，见 SyscfgModel）。

    已声明槽位改绑 = 换通道（`_rewrite_adc_mem_line`）；跟着它共读的孤儿槽位不跟着
    换就会指回一个没有显式 `$assign` 落点的通道——那个脚由 SysConfig 隐式分配，
    静态门禁看不见，真机上可能又撞回别的模块。
    """
    mem = adc_mem_index(binding.declaration.id)
    instances = INSTANCES_BY_SLUG.get(binding.slug, ())
    if not instances:
        return
    leader_path = f"{instances[0]}.adcMem{mem}chansel"
    pairs = followers.get(leader_path)
    if not pairs:
        return
    channel: int | None = None
    for line in lines:
        match = _ADC_MEM_RE.match(line)
        if match is not None and match.group("path") == leader_path:
            channel = _adc_mem_channel(line)
            break
    if channel is None:
        return  # 母版漂移：已声明槽位的 chansel 行不在（改写那边已大声失败）
    for index, line in enumerate(lines):
        match = _ADC_MEM_RE.match(line)
        if match is not None and match.group("path") in pairs:
            lines[index] = _with_adc_channel(line, channel)


def parse_syscfg(text: str) -> SyscfgModel:
    """mspm0.syscfg 全文 → 一次解析产物（独占文法，唯一解析实现）。

    逐行识别四类文法：实例声明（addInstance）、`$assign` 赋值、关联引脚**符号名**
    （`associatedPins[n].$name`）、ADC 通道行（`adcMem<N>chansel`，由
    `_ADC_MEM_RE` 在 rewrite 侧消费）；模块声明（addModule）不在这条扫描里——
    它归 `prune`（`_MODULE_DECL_RE`）。行列表原样保留（splitlines keepends）供
    prune / rewrite 行级改写与 serialize 往返。`adc_followers` 恒空（跟随关系
    只在 prune 里产生）。
    """
    lines = text.splitlines(keepends=True)
    instances: dict[str, SyscfgInstance] = {}
    assigns: list[SyscfgAssign] = []
    pin_names: dict[str, list[str]] = {}
    for i, line in enumerate(lines):
        m = _INSTANCE_DECL_RE.match(line)
        if m:
            instances[m.group("instance")] = SyscfgInstance(
                name=m.group("instance"), module=m.group("module"), line=i
            )
            continue
        m = _SYSCFG_ASSIGN_RE.match(line)
        if m:
            assigns.append(
                SyscfgAssign(path=m.group("path"), pin=m.group("pin"), line=i)
            )
            continue
        m = _SYSCFG_PIN_NAME_RE.match(line)
        if m:
            pin_names.setdefault(m.group("instance"), []).append(m.group("name"))
    return SyscfgModel(
        lines=lines,
        instances=instances,
        assigns=assigns,
        pin_names={name: tuple(names) for name, names in pin_names.items()},
    )


def syscfg_path_matches(
    decl_type: str, role_id: str, slug: str, path: str
) -> bool:
    """槽位身份原语：角色类型 → `$assign` 路径匹配（与旧 _mspm0_path_matches
    口径一致，校验侧与写侧共用）。

    GPIO 组角色（gpio_out/gpio_in/enc）落在 `<实例>.associatedPins[n].pin`，
    同值多行时用 slug 反查消费实例名（syscfg_instances 单源表）区分——
    STEP_MOTOR SLP2 只认 STEP_MOTOR.*，HUIDU R3 只认 HUIDU.*。外设角色
    落点路径尾字段（txPin/rxPin/sclPin/sdaPin/ccp0Pin/ccp1Pin）按 slug
    反查消费实例区分（批次 4 ESPCI 前次；批量 10 DCC_100_PWM2/L298N_PWM
    同 TIMG12/PA14——pwm 尾字段不再唯一）。
    """
    if decl_type in ("gpio_out", "gpio_in", "enc"):
        if not (".associatedPins[" in path and path.endswith(".pin")):
            return False
        instance = path.split(".associatedPins[", 1)[0]
        return instance in INSTANCES_BY_SLUG.get(slug, ())
    if decl_type in ("uart_tx", "uart_rx", "i2c_scl", "i2c_sda"):
        # 外设角色默认值同脚时（module-polish/01：DEBUG_UART 与 UWB_UART
        # 同 UART2/PA23），仅尾字段（txPin 等）不再唯一——按 slug 反查
        # syscfg 实例名区分，与 GPIO 组同款。
        instance = path.split(".peripheral.", 1)[0]
        return instance in INSTANCES_BY_SLUG.get(slug, ())
    if decl_type == "pwm":
        # 外设角色默认值同脚时（wiki-modules-batch10/03：DCC_100_PWM2 与
        # L298N_PWM 同 TIMG12/PA14），仅尾字段（ccp0Pin 等）不再唯一——按
        # slug 反查 syscfg 实例名区分（与 uart/i2c 同款；C0/C1 通道判据先
        # 行保留；带 pwm 角色的 slug 必须已入 INSTANCE_CONSUMERS——
        # 未登记 = 数据漂移，此处大声失败而非掩蔽）。
        if role_id.endswith("_C0"):
            tail_ok = path.endswith(".ccp0Pin")
        elif role_id.endswith("_C1"):
            tail_ok = path.endswith(".ccp1Pin")
        else:
            tail_ok = path.endswith((".ccp0Pin", ".ccp1Pin"))
        instance = path.split(".peripheral.", 1)[0]
        return tail_ok and instance in INSTANCES_BY_SLUG[slug]
    if decl_type == "adc":
        # adc 落点 = `<实例>.peripheral.adcPin<N>`（N = 通道号，TI 命名）；
        # 实例名（ADC12_0）从消费表反查，多实例时按 slug 过滤。
        if not re.search(r"\.adcPin\d+$", path):
            return False
        instance = path.split(".peripheral.", 1)[0]
        return instance in INSTANCES_BY_SLUG.get(slug, ())
    return False


def _locate_mspm0_site(
    lines: list[str],
    line_nos: Sequence[int],
    default: str,
    binding: "ResolvedBinding",
) -> int:
    """默认引脚值 → 唯一槽位行号。同值多行（默认重叠布局）时按角色类型的
    落点路径尾形过滤：gpio 组 → associatedPins[n].pin、uart_tx → txPin、
    i2c_scl → sclPin、pwm → ccp0/ccp1Pin（按角色 id 的 C0/C1 通道）。过滤后
    仍非唯一 = 母版漂移，大声失败。"""
    if len(line_nos) == 1:
        return line_nos[0]
    if not line_nos:
        raise SyscfgModelError(
            f"角色默认引脚 {default} 在母版 {MSPM0_SYSCFG_FILENAME} 中没有"
            f"落点——声明默认值与 syscfg 漂移，请核对工单 01 数据"
        )
    candidates: list[int] = []
    for line_no in line_nos:
        m = _SYSCFG_ASSIGN_RE.match(lines[line_no])
        assert m is not None  # sites 收录时已匹配过
        if syscfg_path_matches(
            binding.declaration.type,
            binding.declaration.id,
            binding.slug,
            m.group("path"),
        ):
            candidates.append(line_no)
    if len(candidates) == 1:
        return candidates[0]
    raise SyscfgModelError(
        f"角色默认引脚 {default} 在母版 {MSPM0_SYSCFG_FILENAME} 中的落点不是"
        f"唯一一行（找到 {len(line_nos)} 行，路径形过滤后剩"
        f" {len(candidates)} 行）——声明默认值与 syscfg 漂移，请核对工单 01"
        f"数据"
    )


def adc_mem_index(role_id: str) -> int:
    """adc 角色 id 尾 `_CH<N>` → ADC12 MEM 索引（ADC_CH0 → 0、ADC_CH1 → 1）。

    非 _CH 尾形 = 声明漂移，大声失败（母版/模块数据错，宁明不默）。
    两处消费：本模块的绑定改写（换槽位 / 换通道行），与 `syscfg_prune` 的
    「本趟声明了哪些 MEM 槽位」（孤儿槽位让位判据）。
    """
    match = re.search(r"_CH(\d+)$", role_id)
    if match is None:
        raise SyscfgModelError(
            f"adc 角色 {role_id} 的 id 不以 _CH<N> 结尾——无法推导 ADC12 "
            f"MEM 槽位（模块 manifest 漂移）"
        )
    return int(match.group(1))


def _adc_slot_head(head: str, binding: "ResolvedBinding") -> str:
    """$assign 行 head（含路径）按绑定通道换 adcPin 槽位名：adcPin3 → adcPin1。

    通道号从绑定脚能力实例解析（与 _rewrite_adc_mem_line 同源）；head 不含
    adcPin 槽位 = 母版漂移，大声失败。"""
    channel = _binding_adc_channel(binding)
    if not re.search(r"\.adcPin\d+\.\$assign\s*=\s*$", head):
        raise SyscfgModelError(
            f"绑定 {binding.role_key} 的 $assign 路径不含 adcPin 槽位"
            f"（{head.strip()}）——母版漂移，请核对"
        )
    return re.sub(
        r"\.adcPin\d+\.\$assign\s*=\s*$",
        f".adcPin{channel}.$assign = ",
        head,
    )


def _rewrite_adc_mem_line(
    lines: list[str], binding: "ResolvedBinding"
) -> None:
    """adc 绑定连带改写 `<实例>.adcMem<N>chansel` 通道行（b1-adc-servo/01）。

    换引脚 = 换 ADC 通道（A0_<M> 与 DL_ADC12_INPUT_CHAN_<M> 对应）：$assign
    落点行已在 rewrite 主循环换成新引脚，此处把对应 MEM 的 chansel 行换成
    新引脚通道号。通道号从绑定脚能力实例解析（类型级推导，如 PA26 → A0_1）；
    A1_* 组 v1 不支持，大声失败。通道行缺失 = 母版漂移，大声失败。
    """
    mem = adc_mem_index(binding.declaration.id)
    channel = _binding_adc_channel(binding)
    instances = INSTANCES_BY_SLUG.get(binding.slug, ())
    if not instances:
        raise SyscfgModelError(
            f"绑定 {binding.role_key} 的模块没有 syscfg ADC 实例登记"
            f"（syscfg_instances 漂移）"
        )
    path = f"{instances[0]}.adcMem{mem}chansel"
    for i, line in enumerate(lines):
        m = _ADC_MEM_RE.match(line)
        if m is None or m.group("path") != path:
            continue
        new_value = f"DL_ADC12_INPUT_CHAN_{channel}"
        if m.group("value") != new_value:
            lines[i] = (
                f'{m.group("head")}"{new_value}"'
                f'{m.group("tail")}{m.group("eol") or ""}'
            )
        return
    raise SyscfgModelError(
        f"绑定 {binding.role_key} 的通道行 {path} 不在母版"
        f" {MSPM0_SYSCFG_FILENAME} 中——母版漂移，请核对"
    )


def _binding_adc_channel(binding: "ResolvedBinding") -> int:
    """绑定脚能力实例 → ADC 通道号（A0_3 → 3）；多实例取首个（同脚同通道
    组，确定性）；A1_* 或缺失 = 大声失败。"""
    for instance in binding.instances:
        m = _ADC_CHAN_RE.match(instance)
        if m:
            return int(m.group(1))
    raise SyscfgModelError(
        f"绑定 {binding.role_key} 的引脚 {binding.pin} 没有 A0_* 通道实例"
        f"（实例 {'、'.join(binding.instances) or '无'}）——v1 只支持"
        f" A0 通道组（A1_* 留待后续）"
    )


def _peripheral_path(assign_path: str) -> str | None:
    """$assign 路径 → 同实例 peripheral 路径：IMU601.peripheral.txPin →
    IMU601.peripheral；GPIO 组 pin 路径（…associatedPins[n].pin）返回 None
    （调用方不处理 gpio 组）。"""
    for field in _PERIPHERAL_PIN_FIELDS:
        if assign_path.endswith("." + field):
            return assign_path[: -len(field) - 1]
    return None


def _mspm0_instance_for_binding(
    role_key: str, instances: tuple[str, ...], current_peripheral: str
) -> str:
    """多实例候选里选一个写 peripheral：优先与母版现值相同（最小改动、换脚
    不动外设），否则取首个（绑定脚 token 序，确定性）。"""
    if not instances:
        raise SyscfgModelError(
            f"绑定 {role_key} 需要改写外设实例，但没有可用的能力实例"
            f"（数据漂移，请核对板定义 token）"
        )
    if current_peripheral:
        for instance in instances:
            if _mspm0_peripheral_of(instance) == current_peripheral:
                return instance
    return instances[0]


def _mspm0_peripheral_of(instance: str) -> str:
    """实例 token → syscfg peripheral 值：TIMG12_C0 → TIMG12、UART1 → UART1、
    I2C1 → I2C1。"""
    if instance.startswith(("TIMG", "TIMA")):
        return instance.split("_", 1)[0]
    return instance
