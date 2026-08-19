"""mspm0.syscfg 文件模型（架构评审 ② 落地）：独占文法 + 一次解析 + 槽位身份。

母版 mspm0.syscfg 的「文件格式知识」曾散在三处：syscfg_prune 拥有实例声明
文法、pinwriter 拥有 `$assign` 文法与路径匹配、槽位身份在 pin_bindings 又
实现了一遍。本模块把它们收敛成单一文件模型：

- `parse_syscfg` 独占两份文法（实例声明 addInstance / 模块声明 addModule /
  `$assign` 赋值），一次解析为 `SyscfgModel`；
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
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .syscfg_instances import INSTANCE_CONSUMERS, INSTANCES_BY_SLUG

if TYPE_CHECKING:
    from .pin_bindings import ResolvedBinding

__all__ = [
    "MSPM0_SYSCFG_FILENAME",
    "SyscfgAssign",
    "SyscfgInstance",
    "SyscfgModel",
    "SyscfgModelError",
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


@dataclass
class SyscfgModel:
    """mspm0.syscfg 的一次解析产物。

    prune 与 rewrite 是对同一解析的两个操作（产出新的 SyscfgModel；rewrite
    无生效绑定时返回原模型），to_text 是唯一回写出口——先后关系由调用方
    pipeline 构造保证。
    """

    lines: list[str]
    instances: dict[str, SyscfgInstance]  # 实例名 -> 实例声明
    assigns: list[SyscfgAssign]  # 全部 $assign 落点（行序）

    def to_text(self) -> str:
        """serialize：行列表拼回全文（splitlines keepends 无损往返）。"""
        return "".join(self.lines)

    def prune(self, selected_slugs: Iterable[str]) -> "SyscfgModel":
        """按选中模块裁剪（对同一解析的 prune 操作，与旧 syscfg_prune 逐字节
        等价）：实例的消费模块集与 selected_slugs 交集为空 → 裁掉该实例的
        `const X = MOD.addInstance();` 行与所有 `X.` 配置行；某模块变量
        （UART/I2C/TIMER/GPIO/PWM）的全部实例被裁 → 连 addModule 行一起裁。
        Board/SYSCTL 与文件头注释不动。产出新的 SyscfgModel。"""
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
        return parse_syscfg("".join(kept))

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


def parse_syscfg(text: str) -> SyscfgModel:
    """mspm0.syscfg 全文 → 一次解析产物（独占文法，唯一解析实现）。

    逐行识别三类文法：实例声明（addInstance）、模块声明（addModule）、
    `$assign` 赋值；行列表原样保留（splitlines keepends）供 prune / rewrite
    行级改写与 serialize 往返。
    """
    lines = text.splitlines(keepends=True)
    instances: dict[str, SyscfgInstance] = {}
    assigns: list[SyscfgAssign] = []
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
    return SyscfgModel(lines=lines, instances=instances, assigns=assigns)


def syscfg_path_matches(
    decl_type: str, role_id: str, slug: str, path: str
) -> bool:
    """槽位身份原语：角色类型 → `$assign` 路径匹配（与旧 _mspm0_path_matches
    口径一致，校验侧与写侧共用）。

    GPIO 组角色（gpio_out/gpio_in/enc）落在 `<实例>.associatedPins[n].pin`，
    同值多行时用 slug 反查消费实例名（syscfg_instances 单源表）区分——
    STEP_MOTOR SLP2 只认 STEP_MOTOR.*，HUIDU R3 只认 HUIDU.*。外设角色
    落点路径尾字段唯一（txPin/rxPin/sclPin/sdaPin/ccp0Pin/ccp1Pin）。
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
        if role_id.endswith("_C0"):
            return path.endswith(".ccp0Pin")
        if role_id.endswith("_C1"):
            return path.endswith(".ccp1Pin")
        return path.endswith((".ccp0Pin", ".ccp1Pin"))
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


def _adc_mem_index(role_id: str) -> int:
    """adc 角色 id 尾 `_CH<N>` → ADC12 MEM 索引（ADC_CH0 → 0、ADC_CH1 → 1）。

    非 _CH 尾形 = 声明漂移，大声失败（母版/模块数据错，宁明不默）。
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
    mem = _adc_mem_index(binding.declaration.id)
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
