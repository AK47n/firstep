"""引脚绑定：载荷解析与校验（板级引脚配置工单 02 机制层）。

bindings 载荷 = `{"<slug>.<role_id>": "<PIN>"}`（spec 板级引脚配置）——本模块
是绑定的唯一校验出口：角色存在于选中模块声明（manifest pins）、引脚存在于
板定义排针（boards.board_pin）、能力合法（boards.pin_supports；
boards.pin_capability_instances 推导实例）。校验通过产出 ResolvedBinding——
写侧渲染器 / 改写器只吃已解析结构，不再自判形状（工单 02 文件边界：模型
归本模块）。

能力口径（平台 × 类型分级，ADR 0011 / ADR 0012）：
- stm32 pwm / enc / uart = **类型级**：绑定引脚须有 ≥1 个 pwm:* / enc:* /
  uart_tx:* / uart_rx:* token，实例随**绑定引脚**推导喂渲染器（pwm 换实例
  = 宏值变化，库零改动——motor_stm32.c 吃宏、ml_pwm 支持 TIM2/3/4 全通道；
  enc 换线 = _LINE/_EXTI 宏跟随绑定，motor 按线号条件编译 handler——工单
  pin-full-unlock/01，异口同线冲突由生成门禁 exti_line_conflicts 拦；uart
  换实例 = _UART/_INST/引脚宏跟随绑定 + USARTx_IRQ_CALLS 重分组——工单
  pin-full-unlock/02，TX/RX 对同实例约束在本模块、实例冲突由生成门禁
  uart_instance_conflicts 拦）。
- mspm0 uart / i2c = **类型级**（ADR 0012 工单 03）：绑定引脚须有 ≥1 个
  uart_tx:* / uart_rx:* / i2c_scl:* / i2c_sda:* token，实例随绑定引脚推导
  喂写侧（syscfg peripheral 字段改写，实例名不动 → 模块代码零改动）；
  TX/RX 与 SCL/SDA 成对同实例约束在本模块（机制与工单 02 同款），实例
  冲突由生成门禁 uart_instance_conflicts 拦（平台通用）。
- mspm0 pwm = **全类型级**（ADR 0012 工单 04，跨族放开）：有 pwm token 且
  通道（角色 id 尾 `_C0`/`_C1`）匹配的脚可绑；PWMAB 两通道同实例约束在本
  模块（_check_mspm0_pwm_channel_pairs，C0/C1 实例基名交集必须非空）。
- 其余（mspm0 gpio / enc / 其余类型 + stm32 其余类型）= strict-all：绑定引脚
  须支持默认引脚的**全部**实例。mspm0 gpio 组另有同端口门禁（step_motor
  四脚单端口宏）。宁严勿假绿：无实例类型（gpio/enc-mspm0）只查类型。

政策：
- 缺省 = 全默认：bindings 缺省或未覆盖的角色按声明默认值生成；必选角色允许
  缺省（走默认）。绑定值 == 默认值的条目保留在清单里（写侧按 no-op 跳过，
  逐字节契约不破）。
- 重复绑定不拦（同脚多角色不拒；是否合法由 `_shared_groups` 标注区分——
  同 I2C 总线 / 同 UART 实例 / 同 syscfg 器件实例 = 合法共享 kind=share，
  分属不同外设 = kind=conflict（物理不通，前端提示改线），工单 pin-share-rule/01）；
  板外脚（如 mspm0 的 PB4/PB5 不在排针）绑定 = 未知引脚 400。
- mspm0 槽位互斥：同一默认引脚且同一 syscfg 落点路径（母版 $assign 引脚值
  唯一为常态；STEP_MOTOR SLP2/DIR2 与 HUIDU R3/R4 默认重叠 PB6/PB7 属刻意
  重叠，路径不同不互斥）的两个角色绑到不同引脚 = 冲突 400——stm32 各角色
  宏族独立（GRAY_D1 与 DIP0 同默认 PB12 但宏不同），不拦。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Sequence

from .boards import Board, BoardPin, board_pin, pin_capability_instances, pin_supports
from .manifest import ModuleManifest, PinDeclaration
from .syscfg_instances import INSTANCES_BY_SLUG
from .platforms import PLATFORM_MSPM0, PLATFORM_STM32


class PinBindingError(ValueError):
    """引脚绑定载荷非法（键格式 / 未知角色 / 未知引脚 / 能力不符 / 槽位冲突）。"""


@dataclass(frozen=True)
class ResolvedBinding:
    """一条通过校验的绑定：写侧只吃它（渲染器 / 改写器不再自判形状）。

    instances = 角色实例（pin_capability_instances 推导；stm32 pwm / enc
    类型级 = 绑定引脚实例（ADR 0011 / ADR 0012），其余 = 默认引脚能力
    token 的实例；gpio_out/gpio_in 与 mspm0 enc 等无实例类型为空元组）。
    stm32 渲染器需要单实例推导宏值（多实例 = 数据歧义，渲染处大声失败）。
    """

    slug: str
    declaration: PinDeclaration
    pin: str  # 绑定引脚（板定义排针上的脚）
    instances: tuple[str, ...] = ()  # 默认引脚能力 token 实例（无实例类型 = 空）

    @property
    def role_key(self) -> str:
        """载荷键形态（<slug>.<role_id>，报错文案用）。"""
        return f"{self.slug}.{self.declaration.id}"


def resolve_bindings(
    manifests: Sequence[ModuleManifest],
    platform: str,
    board: Board,
    raw: Mapping[str, str] | None,
) -> tuple[ResolvedBinding, ...]:
    """bindings 载荷 → 校验后的绑定清单；任何非法即抛 PinBindingError（400 中文）。

    校验三查：键格式 `<slug>.<role_id>` 且角色在选中模块的该平台声明里 /
    引脚在板定义排针（板外脚 = 未知引脚）/ 能力合法（stm32 pwm / enc /
    uart_tx / uart_rx = 类型级：绑定引脚须有 ≥1 个对应类型 token，实例随
    绑定引脚推导；stm32 uart 另查 TX/RX 对同实例约束——两脚有效实例集
    （绑定脚 / 未绑默认引脚）交集非空，空 = 400 中文成对绑定；其余
    strict-all：绑定引脚须支持默认引脚能力 token 的**全部**实例——mspm0
    复用标注多实例引脚的先例：motor.PWMAB_C0 默认 PA12 有
    pwm:TIMG0_C0 + pwm:TIMA0_C3，仅 TIMA0_C3 的脚如 PA28 会让 SysConfig
    路由失败，宁严勿假绿）。mspm0 同默认引脚两角色绑不同脚 = 槽位冲突互斥
    （syscfg 单落点）。顺序 = 载荷插入顺序（dict 保序，写侧覆盖顺序确定性）。
    """
    if not raw:
        return ()
    if not isinstance(raw, Mapping):
        raise PinBindingError(
            "bindings 必须是 JSON 对象（形如 {\"模块.角色\": \"引脚\"}）"
        )

    by_slug = {m.slug: m for m in manifests}
    roles: dict[tuple[str, str], PinDeclaration] = {}
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for decl in entry.pins:
            roles[(manifest.slug, decl.id)] = decl

    resolved: list[ResolvedBinding] = []
    for key, pin in raw.items():
        if not isinstance(key, str) or key.count(".") != 1:
            raise PinBindingError(
                f"绑定键格式非法：{key!r}（应为 <模块>.<角色>，如 motor.MOTOR_A_PWM）"
            )
        if not isinstance(pin, str) or not pin.strip():
            raise PinBindingError(f"绑定 {key} 的引脚值必须是非空字符串")
        pin = pin.strip()
        slug, role_id = key.split(".")
        if not slug or not role_id:
            raise PinBindingError(
                f"绑定键格式非法：{key!r}（应为 <模块>.<角色>，如 motor.MOTOR_A_PWM）"
            )
        if slug not in by_slug:
            raise PinBindingError(
                f"绑定角色不存在：{key}（模块 {slug} 不在所选模块集内）"
            )
        declaration = roles.get((slug, role_id))
        if declaration is None:
            raise PinBindingError(
                f"绑定角色不存在：{key}（模块 {slug} 的平台 {platform} "
                f"声明里没有该角色）"
            )
        bound = board_pin(board, pin)
        if bound is None:
            raise PinBindingError(
                f"绑定 {key} 的引脚 {pin} 不存在（不在 {board.name} 排针引脚集内）"
            )
        # 类型级（ADR 0011 / ADR 0012 Tier A/B）：stm32 pwm / enc / uart 与
        # mspm0 uart / i2c / pwm——实例随**绑定引脚**推导喂写侧（stm32 pwm
        # 换实例 = 宏值变化、enc 换线 = _LINE/_EXTI 宏跟随、uart 换实例 =
        # _UART/_INST/引脚宏跟随；mspm0 uart/i2c/pwm 换实例 = syscfg
        # peripheral 字段改写，实例名不动 → 模块代码零改动）；无对应 token
        # 的脚仍拒（类型级下限）。mspm0 pwm 通道匹配的脚跨族可绑（工单 04，
        # 全类型级放开；PWMAB 两通道同实例门禁在循环后查）。其余 strict-all：
        # 实例 = 默认引脚能力 token 的实例（板外默认如 PB4/PB5 无默认引脚 →
        # 实例空 → 只查类型）；多实例 = 全部命中（any-of 会放行 SysConfig
        # 路由必炸的绑定——工单 02 红证已验）
        if platform == PLATFORM_STM32 and declaration.type in (
            "pwm",
            "enc",
            "uart_tx",
            "uart_rx",
            "adc",
        ):
            instances = _type_level_instances(
                bound, declaration.type, key, pin
            )
        elif platform == PLATFORM_MSPM0 and declaration.type in (
            "uart_tx",
            "uart_rx",
            "i2c_scl",
            "i2c_sda",
            "adc",
        ):
            instances = _type_level_instances(
                bound, declaration.type, key, pin
            )
        elif platform == PLATFORM_MSPM0 and declaration.type == "pwm":
            instances = _mspm0_pwm_instances(
                bound, declaration, key, pin
            )
        else:
            default_bound = board_pin(board, declaration.default)
            instances = (
                pin_capability_instances(default_bound, declaration.type)
                if default_bound is not None
                else ()
            )
            if instances:
                if not all(
                    pin_supports(bound, declaration.type, instance)
                    for instance in instances
                ):
                    raise PinBindingError(
                        f"绑定 {key} 的引脚 {pin} 不能担任该角色：需要"
                        f" {declaration.type} 实例 {'、'.join(instances)}"
                        f"（角色实例随默认引脚 {declaration.default} 锁定）"
                    )
            elif not pin_supports(bound, declaration.type):
                raise PinBindingError(
                    f"绑定 {key} 的引脚 {pin} 不支持角色类型 {declaration.type}"
                )
        resolved.append(
            ResolvedBinding(
                slug=slug,
                declaration=declaration,
                pin=pin,
                instances=instances,
            )
        )

    if platform == PLATFORM_MSPM0:
        _check_slot_conflicts(resolved)
        _check_mspm0_gpio_port_groups(board, roles, raw)
        _check_mspm0_pwm_channel_pairs(board, roles, raw)
    if platform in (PLATFORM_STM32, PLATFORM_MSPM0):
        _check_paired_role_instances(board, roles, raw)
    return tuple(resolved)


def _type_level_instances(
    bound: BoardPin, role_type: str, key: str, pin: str
) -> tuple[str, ...]:
    """类型级角色：绑定引脚须有 ≥1 个对应类型 token，实例随绑定引脚推导。"""
    instances = pin_capability_instances(bound, role_type)
    if not instances:
        raise PinBindingError(
            f"绑定 {key} 的引脚 {pin} 不支持角色类型 {role_type}"
        )
    return instances


def _mspm0_pwm_instances(
    bound: BoardPin,
    declaration: PinDeclaration,
    key: str,
    pin: str,
) -> tuple[str, ...]:
    """mspm0 pwm 全类型级（ADR 0012 Tier B 工单 04）：有 pwm token 的脚可绑
    （跨族放开），角色通道（id 尾 `_C0`/`_C1`）仍须匹配——C0 角色只收
    *_C0 实例（*_C0N 互补通道不匹配，SysConfig ccp0Pin 路由不上）。多实例
    匹配全部随绑定推导喂写侧（写侧优先选与母版 peripheral 现值相同的实例 =
    最小改动；否则取首个）。PWMAB 两通道同实例约束在 resolve 循环后由
    _check_mspm0_pwm_channel_pairs 查。
    """
    channel = _pwm_role_channel(declaration.id)
    bound_instances = pin_capability_instances(bound, "pwm")
    allowed = tuple(
        i
        for i in bound_instances
        if not channel or i.endswith("_" + channel)
    )
    if not allowed:
        raise PinBindingError(
            f"绑定 {key} 的引脚 {pin} 不能担任该角色：需要 pwm 通道"
            f" {channel or '任意'}，此脚 pwm 实例"
            f" {'、'.join(bound_instances) or '无'} 无匹配通道"
        )
    return allowed


def _pwm_role_channel(role_id: str) -> str | None:
    """pwm 角色 id 的通道尾（PWMAB_C0 → C0、DCC_100_PWM2_C0 → C0）。"""
    match = re.search(r"_C(\d+)$", role_id)
    return f"C{match.group(1)}" if match else None


def _pwm_instance_base(instance: str) -> str:
    """pwm 实例基名（TIMA0_C0 → TIMA0、TIMG12_C1 → TIMG12）——两通道同实例
    门禁按基名判交集。"""
    return instance.split("_", 1)[0]


def _check_mspm0_pwm_channel_pairs(
    board: Board,
    roles: dict[tuple[str, str], PinDeclaration],
    raw: Mapping[str, str],
) -> None:
    """mspm0 PWMAB 两通道同实例门禁（ADR 0012 Tier B 工单 04）：同 slug 下
    `_C0`/`_C1` 成对的 pwm 角色，两脚的有效实例集（绑定脚 / 未绑默认脚，
    过滤到各自通道）按实例基名（TIMA0 / TIMG0）交集必须非空——C0/C1 分属
    两外设 = SysConfig 单 peripheral 路由必炸，400 生成前拦。单通道角色
    （DCC_100_PWM2_C0）无对不查；只声明单脚 / 无匹配实例不查（防御路径）。
    """
    pairs: dict[tuple[str, str], dict[str, PinDeclaration]] = {}
    for (slug, role_id), decl in roles.items():
        if decl.type != "pwm":
            continue
        match = re.search(r"^(?P<stem>.+)_C(?P<channel>[01])$", role_id)
        if match is None:
            continue
        pairs.setdefault((slug, match.group("stem")), {})[
            match.group("channel")
        ] = decl

    for (slug, _), feet in pairs.items():
        c0 = feet.get("0")
        c1 = feet.get("1")
        if c0 is None or c1 is None:
            continue
        c0_instances = _pwm_pair_foot_instances(board, raw, slug, c0, "C0")
        c1_instances = _pwm_pair_foot_instances(board, raw, slug, c1, "C1")
        if not c0_instances or not c1_instances:
            continue  # 板外默认等无实例：不查（防御路径）
        c0_bases = {_pwm_instance_base(i) for i in c0_instances}
        c1_bases = {_pwm_instance_base(i) for i in c1_instances}
        if not (c0_bases & c1_bases):
            raise PinBindingError(
                f"绑定 {slug}.{c0.id} / {slug}.{c1.id} 的两通道必须同实例，"
                f"请成对绑定（C0 实例 {'、'.join(sorted(c0_instances))} ×"
                f" C1 实例 {'、'.join(sorted(c1_instances))} 交集为空）——"
                f"PWM 双通道只能挂同一外设实例"
            )


def _pwm_pair_foot_instances(
    board: Board,
    raw: Mapping[str, str],
    slug: str,
    decl: PinDeclaration,
    channel: str,
) -> set[str]:
    """pwm 两通道角色单脚的有效实例集（绑定脚 / 默认脚，过滤通道）。"""
    key = f"{slug}.{decl.id}"
    pin = raw.get(key)
    bound = board_pin(board, pin) if pin is not None else board_pin(board, decl.default)
    if bound is None:
        return set()
    return {
        instance
        for instance in pin_capability_instances(bound, "pwm")
        if instance.endswith("_" + channel)
    }


def _check_paired_role_instances(
    board: Board,
    roles: dict[tuple[str, str], PinDeclaration],
    raw: Mapping[str, str],
) -> None:
    """成对角色同实例约束（ADR 0012 工单 02/03，平台通用）：UART TX/RX 与
    I2C SCL/SDA 同一角色对（同 slug 下同根 id）两脚的有效实例集——绑定脚
    实例（已过类型级校验）/ 未绑默认引脚实例——交集必须非空。空 = 400
    中文"必须同实例，请成对绑定"：单脚换实例必撞另一脚默认实例（换过去 =
    TX/RX 或 SCL/SDA 分属两外设，编译绿运行坏），宁严勿假绿；成对同实例 =
    交集推导喂写侧（两脚实例同源）。只声明单脚 / 无实例（防御路径，真库
    全成对）不查。
    """
    for type_a, type_b, suffix_a, suffix_b, label_a, label_b in (
        ("uart_tx", "uart_rx", "_TX", "_RX", "TX", "RX"),
        ("i2c_scl", "i2c_sda", "_SCL", "_SDA", "SCL", "SDA"),
    ):
        pairs: dict[tuple[str, str], dict[str, PinDeclaration]] = {}
        for (slug, role_id), decl in roles.items():
            if decl.type == type_a and role_id.endswith(suffix_a):
                pairs.setdefault((slug, role_id[: -len(suffix_a)]), {})[
                    type_a
                ] = decl
            elif decl.type == type_b and role_id.endswith(suffix_b):
                pairs.setdefault((slug, role_id[: -len(suffix_b)]), {})[
                    type_b
                ] = decl
        for (slug, _), feet in pairs.items():
            first = feet.get(type_a)
            second = feet.get(type_b)
            if first is None or second is None:
                continue  # 只声明单脚的角色对不查（真库全成对，防御路径）
            first_instances = _pair_foot_instances(board, raw, slug, first)
            second_instances = _pair_foot_instances(board, raw, slug, second)
            if not first_instances or not second_instances:
                continue  # 板外默认等无实例：不查（防御路径）
            if not (first_instances & second_instances):
                raise PinBindingError(
                    f"绑定 {slug}.{first.id} / {slug}.{second.id} 的"
                    f" {label_a}/{label_b} 必须同实例，请成对绑定"
                    f"（{label_a} 实例 {'、'.join(sorted(first_instances))} ×"
                    f" {label_b} 实例 {'、'.join(sorted(second_instances))}"
                    f" 交集为空）"
                )


def _pair_foot_instances(
    board: Board, raw: Mapping[str, str], slug: str, decl: PinDeclaration
) -> set[str]:
    """成对角色单脚的有效实例集：绑定脚实例（raw 有值）/ 默认引脚实例。"""
    key = f"{slug}.{decl.id}"
    pin = raw.get(key)
    bound = board_pin(board, pin) if pin is not None else board_pin(board, decl.default)
    if bound is None:
        return set()
    return set(pin_capability_instances(bound, decl.type))


def _check_mspm0_gpio_port_groups(
    board: Board,
    roles: dict[tuple[str, str], PinDeclaration],
    raw: Mapping[str, str],
) -> None:
    """mspm0 gpio 组同端口门禁（ADR 0012 Tier A 工单 03）：同一模块同类型
    gpio 角色若默认全在同一端口（数据判据 = step_motor 四脚全 GPIOB），则
    它们吃单端口宏（如 STEP_MOTOR_PORT）——有效引脚（绑定值或默认值）必须
    同端口，混端口编译绿运行坏，400 生成前拦。默认就混端口的组（DC_MOTOR /
    HUIDU / 灰度等）走逐脚端口宏，不查。
    """
    groups: dict[tuple[str, str], list[PinDeclaration]] = {}
    for (slug, _), decl in roles.items():
        if decl.type in ("gpio_out", "gpio_in"):
            groups.setdefault((slug, decl.type), []).append(decl)

    for (slug, _), decls in groups.items():
        if len(decls) < 2:
            continue
        default_ports = {_pin_port(d.default) for d in decls}
        if len(default_ports) != 1:
            continue  # 默认混端口 = 逐脚端口宏，无单端口约束
        ports = {_pin_port(raw.get(f"{slug}.{d.id}", d.default)) for d in decls}
        if len(ports) != 1:
            raise PinBindingError(
                f"绑定冲突：{slug} 的 {len(decls)} 个 {decls[0].type} 角色"
                f"（{'、'.join(d.id for d in decls)}）必须绑到同一端口"
                f"（当前 {'、'.join(sorted(ports))}）——该组角色走单端口宏"
                f"（如 STEP_MOTOR_PORT），混端口编译绿运行坏"
            )


def _pin_port(pin: str) -> str:
    """引脚名 → 端口字母（PA15 → A、PB24 → B）。"""
    return pin[1]


def _check_slot_conflicts(resolved: Sequence[ResolvedBinding]) -> None:
    """mspm0 槽位互斥：同一默认引脚 + 同一 syscfg 落点路径，绑到不同引脚 =
    冲突。

    判例：motor.AA 与 key.DC_MOTOR_AA 同默认 PA16 且同属 DC_MOTOR 实例
    （syscfg DC_MOTOR 槽位 AA 单落点），两模块同时选中并绑到不同脚时物理
    互斥——400 大声失败比静默后者覆盖前者诚实。同槽位同引脚不拦（重复共享
    合法）。STEP_MOTOR SLP2/DIR2 与 HUIDU R3/R4 默认同 PB6/PB7 但实例路径
    不同（STEP_MOTOR.* vs HUIDU.*），绑不同脚合法——用户改绑消解重叠。
    """
    by_default: dict[str, list[ResolvedBinding]] = {}
    for binding in resolved:
        by_default.setdefault(binding.declaration.default, []).append(binding)
    for default, group in by_default.items():
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                if left.pin != right.pin and _mspm0_same_slot(left, right):
                    raise PinBindingError(
                        f"绑定冲突：{left.role_key} 与 {right.role_key} 共用同一"
                        f"槽位（默认引脚 {default}）却绑到不同引脚"
                        f" {left.pin}、{right.pin} —— 请绑到同一引脚"
                    )


def _mspm0_same_slot(left: ResolvedBinding, right: ResolvedBinding) -> bool:
    """两绑定是否落同一 syscfg 槽位（与 pinwriter 的路径匹配口径一致）。

    GPIO 组角色：实例名集合有交集（motor 与 key 共享 DC_MOTOR）即可能同槽
    位；STEP_MOTOR 与 HUIDU 无交集 = 默认重叠但槽位不同。外设角色：类型
    尾字段一一对应（pwm 再按角色 id 尾 C0/C1 分通道）。
    """
    lt = left.declaration.type
    rt = right.declaration.type
    if lt in ("gpio_out", "gpio_in", "enc") and rt in (
        "gpio_out",
        "gpio_in",
        "enc",
    ):
        return bool(
            set(INSTANCES_BY_SLUG.get(left.slug, ()))
            & set(INSTANCES_BY_SLUG.get(right.slug, ()))
        )
    if lt != rt:
        return False
    if lt == "pwm":
        return _pwm_channel(left.declaration.id) == _pwm_channel(
            right.declaration.id
        )
    return True


def _pwm_channel(role_id: str) -> str:
    """角色 id 尾 C0/C1 → 通道；非通道形返回原 id（保持同槽位保守判等）。"""
    return role_id.rsplit("_", 1)[-1] if "_" in role_id else role_id


@dataclass(frozen=True)
class AutoAssignResult:
    """自动配置结果（工单 pin-auto-assign/01）：bindings 增量 + 调整说明 +
    保留共享/冲突标注。"""

    bindings: dict[str, str]  # 增量：只含冲突角色新绑定（key → PIN）
    fixed: tuple[str, ...]  # 说明行："<role_key> → <PIN>（原 <old> 冲突，已自动移开）"
    shared: tuple[dict[str, object], ...]  # 同脚多角色标注：{pin, roles, kind, reason}


def auto_assign_bindings(
    manifests: Sequence[ModuleManifest],
    platform: str,
    board: Board,
    raw: Mapping[str, str] | None,
    *,
    resolve_default_conflicts: bool = False,
) -> AutoAssignResult:
    """一键解冲突（工单 pin-auto-assign/01）：确定性贪心求解，零 LLM。

    只动「真冲突」角色（resolve_bindings 校验面，与 /api/bindings/validate
    同源：能力不匹配 / UART TX-RX 成对 / mspm0 槽位互斥 / 类型级实例约束），
    合法共享（同脚多角色，ADR 0010）保留并标注。用户合法绑定与未冲突默认
    脚不动。无冲突 → 空增量 + shared 标注。无解 → PinBindingError（中文
    说明缺什么）。TIM/EXTI/UART 实例级冲突属生成门禁（需 main_c 上下文），
    不在本功能范围。

    算法：逐角色修复（顺序 = 载荷键序）——先试原绑定值（在已修复集合上
    整体 resolve_bindings 验证，合法 = 保留不动）；非法 → 换候选引脚（板
    排针，跳过已占用——自动配置倾向不制造新共享），逐个试绑整体验证，
    首个成功者。唯一校验 = resolve_bindings，不复制判定。

    resolve_default_conflicts（工单 pin-conflict-gate/02）= 「默认×默认撞脚」
    消解相，**缺省关**：只对知道「本次选中了什么」的调用方（生成页引脚卡的
    `/api/bindings/auto`）开。为什么必须是显式开关——全库默认布局本身就是
    「全量实例 + 同选概率最低者重叠」（mspm0 27 组 / stm32 26 组刻意重叠），
    库级 / 纯校验调用方把它们当成「要解的冲突」是无意义的；而选中集里剩下的
    同脚冲突就是真会炸 SysConfig 的那些（生成门禁 syscfg_pin_conflicts 拦下的
    是同一批）。本相：逐组让**一个**角色让位（让位方 = 选中清单里靠后的模块，
    同模块内角色键序最后；已被用户显式绑定的角色不动 = 用户明确选择），移到
    能力匹配、且搬完不再出现在任何冲突组里的首个空闲脚；合法共享
    （`kind="share"`）一律不动；搬不动（无候选脚）= 该组留在 shared 标注里
    如实可见，不谎报成功也不抛错。
    """
    bindings = dict(raw or {})
    # 1. 现状合法 = 无绑定级冲突（含合法共享）：跳过逐角色修复相
    fixed: list[str] = []
    repaired: dict[str, str] = dict(bindings)
    try:
        resolve_bindings(manifests, platform, board, bindings or None)
    except PinBindingError:
        repaired, fixed = _repair_binding_conflicts(
            manifests, platform, board, bindings
        )
    # 2. 默认脚撞脚消解相（只对选中集语义的调用方开，缺省零变化）
    if resolve_default_conflicts:
        repaired, default_fixed = _resolve_default_pin_conflicts(
            manifests, platform, board, repaired, raw or {}
        )
        fixed = fixed + default_fixed
    delta = {
        key: pin for key, pin in repaired.items()
        if (raw or {}).get(key) != pin
    }
    return AutoAssignResult(
        bindings=delta,
        fixed=tuple(fixed),
        shared=_shared_groups(manifests, platform, board, repaired),
    )


def _repair_binding_conflicts(
    manifests: Sequence[ModuleManifest],
    platform: str,
    board: Board,
    bindings: Mapping[str, str],
) -> tuple[dict[str, str], list[str]]:
    """逐角色修复相（工单 pin-auto-assign/01 原算法，逐字抽出）：先试原值
    （整体 resolve_bindings 合法 = 保留），非法 → 换能力匹配的候选脚。"""
    repaired: dict[str, str] = {}
    used: set[str] = set()
    fixed: list[str] = []
    for key, value in bindings.items():
        trial = dict(repaired)
        trial[key] = value
        try:
            resolve_bindings(manifests, platform, board, trial)
        except PinBindingError:
            pass
        else:
            repaired[key] = value
            used.add(value)
            continue
        # 原值非法 → 换脚
        for pin in board.pins:
            if pin.name in used:
                continue
            trial = dict(repaired)
            trial[key] = pin.name
            try:
                resolve_bindings(manifests, platform, board, trial)
            except PinBindingError:
                continue
            repaired[key] = pin.name
            used.add(pin.name)
            fixed.append(f"{key} → {pin.name}（原 {value} 冲突，已自动移开）")
            break
        else:
            raise PinBindingError(
                f"自动配置无法为 {key} 找到可用引脚（能力匹配且未被占用的引脚"
                "不存在或与其余绑定冲突），请手动调整"
            )
    return repaired, fixed


# 默认脚撞脚消解的最大搬动次数（防御性上限：选中集内真冲突组数量级 ~10，
# 全库调用不开本相；上限保证任何输入下都是有限、确定的迭代）
_MAX_DEFAULT_CONFLICT_MOVES = 32


def _default_conflict_groups(
    manifests: Sequence[ModuleManifest],
    platform: str,
    board: Board,
    bindings: Mapping[str, str],
) -> list[dict[str, object]]:
    """当前绑定/默认布局下的物理冲突组（`kind="conflict"`，共享组不算）。"""
    return [
        group
        for group in _shared_groups(manifests, platform, board, bindings)
        if group["kind"] == "conflict"
    ]


def _group_roles(group: Mapping[str, object]) -> list[str]:
    """冲突组的角色键清单（`_shared_groups` 的 roles 字段，形状由它保证）。"""
    roles = group.get("roles")
    return [str(key) for key in roles] if isinstance(roles, list) else []


def _role_entries(
    manifests: Sequence[ModuleManifest],
    platform: str,
    bindings: Mapping[str, str],
) -> list[tuple[str, str, PinDeclaration, str]]:
    """选中角色的生效落点：(角色键, slug, 声明, 生效引脚)。绑定优先、缺省用声明
    默认脚；无默认脚 = 不含（角色键与生效脚的唯一推导出处，`_shared_groups` 与
    默认脚消解相共用——两处各写一遍就会漂移）。"""
    entries: list[tuple[str, str, PinDeclaration, str]] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for decl in entry.pins:
            key = f"{manifest.slug}.{decl.id}"
            pin = bindings.get(key) or decl.default
            if pin:
                entries.append((key, manifest.slug, decl, pin))
    return entries


def _resolve_default_pin_conflicts(
    manifests: Sequence[ModuleManifest],
    platform: str,
    board: Board,
    bindings: Mapping[str, str],
    explicit: Mapping[str, str],
) -> tuple[dict[str, str], list[str]]:
    """默认脚撞脚消解相（工单 pin-conflict-gate/02）：逐组搬一个让位角色。

    让位方 = 该组成员所属模块在选中清单里**靠后**者（同模块内角色键序最后），
    且**未被用户显式绑定**（显式 = 用户明确选择，只标注不搬）；组内全是显式
    绑定 → 整组不动。候选脚 = 板定义引脚序里「**空闲**（本次选中集内没有任何
    其它角色用它，含合法共享的同伴——同一实例的三条落点挤一个脚是接线错，
    真机上连 SysConfig 都过不去）+ resolve_bindings 试绑合法 + 搬完该角色不再
    出现在任何冲突组 + 不把冲突搬到别处」的首个脚。

    让位方按偏好序**逐个试**（先靠后模块，搬不动换下一个）：UART TX/RX 这类
    成对角色单搬一个过不了成对校验，得让组里另一侧让位——只钉「第一个候选」
    会在真机上留下解不掉的两组（2026H 的 PA28/PA31 实测）。搬不动 → 该组留给
    shared 标注（不抛错：一键配置是尽力而为，拦生成是门禁的活）。
    """
    repaired = dict(bindings)
    fixed: list[str] = []
    order = {manifest.slug: index for index, manifest in enumerate(manifests)}
    given_up: set[str] = set()

    def rank(key: str) -> tuple[int, str]:
        slug = key.split(".", 1)[0]
        return (order.get(slug, -1), key)

    for _ in range(_MAX_DEFAULT_CONFLICT_MOVES):
        conflicts = _default_conflict_groups(manifests, platform, board, repaired)
        target = next((g for g in conflicts if g["pin"] not in given_up), None)
        if target is None:
            break
        movable = [key for key in _group_roles(target) if key not in explicit]
        pin: str | None = None
        victim: str | None = None
        for candidate in sorted(movable, key=rank, reverse=True):
            pin = _first_pin_without_conflict(
                candidate, manifests, platform, board, repaired, conflicts
            )
            if pin is not None:
                victim = candidate
                break
        if victim is None or pin is None:
            given_up.add(str(target["pin"]))
            continue
        repaired[victim] = pin
        others = "、".join(key for key in _group_roles(target) if key != victim)
        fixed.append(f"{victim} → {pin}（原 {target['pin']} 与 {others} 冲突，已自动移开）")
    return repaired, fixed


def _first_pin_without_conflict(
    victim: str,
    manifests: Sequence[ModuleManifest],
    platform: str,
    board: Board,
    bindings: Mapping[str, str],
    conflicts: Sequence[Mapping[str, object]],
) -> str | None:
    """让位角色的候选脚：板定义引脚序里「空闲 + 能力匹配 + 搬完不再冲突」的首个脚。

    空闲 = 本次选中集内没有别的角色落脚（其它角色的默认脚也算占用——母版默认
    布局按「同选概率最低者重叠」铺满，但**选中集内**没被别的选中角色用掉的脚
    就是生成时 prune 之后真正空出来的脚，正是可搬家当）。
    """
    before = len(conflicts)
    occupied = {
        pin for key, _slug, _decl, pin in _role_entries(manifests, platform, bindings)
        if key != victim
    }
    for pin in board.pins:
        if pin.name in occupied:
            continue
        trial = dict(bindings)
        trial[victim] = pin.name
        try:
            resolve_bindings(manifests, platform, board, trial)
        except PinBindingError:
            continue
        after = _default_conflict_groups(manifests, platform, board, trial)
        if any(victim in _group_roles(group) for group in after):
            continue
        if len(after) > before:
            continue  # 别把冲突搬到别处
        return pin.name
    return None


def _role_resource_keys(slug: str, decl: PinDeclaration, bound: BoardPin | None) -> set[str]:
    """角色的「物理资源键」集（同脚多角色 合法共享/冲突 判据，工单
    pin-share-rule/01——_shared_groups 与前端 pinShareClass 同口径）：

    - uart_tx / uart_rx：绑定/默认引脚的能力实例（UART_1 / UART_3 …）——
      同一串口外设的链路才能共用（zigbee 家族 / DIGIT+COORD+UWB 共 UART_1）；
    - i2c_scl / i2c_sda：能力实例（I2C0 …；stm32 无实例 token = 空集）——
      I2C 总线按多挂语义单独判（_shared_groups 首分支），不依赖本键；
    - gpio_out / gpio_in：模块的 syscfg 实例集（INSTANCES_BY_SLUG）——
      同一器件/总线（HUIDU 灰度 8 路 / LED_BEEP / DC_MOTOR …）才能共用；
    - 其余（pwm / enc / adc / spi …）= 空集：同脚即物理冲突（两路输出/两
      个通道不可并——共用会短路或混线，除非两角色描述同一信号）。
    """
    if bound is None:
        return set()
    if decl.type in ("uart_tx", "uart_rx", "i2c_scl", "i2c_sda"):
        return set(pin_capability_instances(bound, decl.type))
    if decl.type in ("gpio_out", "gpio_in"):
        return set(INSTANCES_BY_SLUG.get(slug, ()))
    return set()


def _shared_groups(
    manifests: Sequence[ModuleManifest],
    platform: str,
    board: Board,
    bindings: Mapping[str, str],
) -> tuple[dict[str, object], ...]:
    """同脚多角色组的 共享/冲突 标注（工单 pin-share-rule/01）：按「物理资源
    键」交集判定——同一 I2C 总线（HMC5883L / MPU6050 可同挂 SCL/SDA）、同一
    UART 实例、同一 syscfg 器件实例 = 合法共享（kind=share）；其余同脚 =
    分属不同外设（kind=conflict，物理不通，请改线）。只对在板上存在的引脚
    标注。旧行为「任意同脚多角色都算合法共享」已废弃（电机 DIR 与按键、
    DIP 拨码与灰度同脚等实际不可共用）。
    """
    groups: dict[str, list[tuple[str, str, PinDeclaration]]] = {}
    for key, slug, decl, pin in _role_entries(manifests, platform, bindings):
        groups.setdefault(pin, []).append((key, slug, decl))
    shared: list[dict[str, object]] = []
    for pin, roles in sorted(groups.items()):
        if len(roles) < 2 or board.pin_index.get(pin) is None:
            continue
        bound = board.pin_index[pin]
        types = {decl.type for _, _, decl in roles}
        if types <= {"i2c_scl", "i2c_sda"}:
            kind, reason = (
                "share",
                "I2C 总线共享（HMC5883L / MPU6050 等可同挂 SCL/SDA，协议允许）",
            )
        else:
            keysets = [
                _role_resource_keys(slug, decl, bound) for _, slug, decl in roles
            ]
            common = set.intersection(*keysets) if keysets else set()
            if common and types & {"uart_tx", "uart_rx"}:
                kind, reason = "share", "同一串口链路共享（共用同一 UART 实例）"
            elif common:
                kind, reason = "share", "共用同一器件/总线（同一实例，共享合法）"
            else:
                kind, reason = (
                    "conflict",
                    "同引脚但分属不同外设（物理不通）——请改线",
                )
        shared.append(
            {
                "pin": pin,
                "roles": [key for key, _, _ in roles],
                "kind": kind,
                "reason": reason,
            }
        )
    return tuple(shared)
