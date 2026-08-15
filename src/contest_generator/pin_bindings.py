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
- 其余（mspm0 全部类型 + stm32 其余类型）= strict-all：绑定引脚须支持默认
  引脚的**全部**实例——mspm0 复用标注多实例引脚（motor.PWMAB_C0 默认 PA12
  有 pwm:TIMG0_C0 + pwm:TIMA0_C3）只有同双实例的引脚才可绑（现状仅 PA12
  自身 = 锁死）。宁严勿假绿：syscfg 改写器只换 $assign 不改外设
  （PWMAB.peripheral = TIMG0 不动），绑到只有 TIMA0_C3 的脚（如 PA28）会让
  SysConfig 路由失败——strict-all 把这类"界面显示兼容但构建必炸"的绑定挡
  在生成前。单实例类型（uart/i2c）与无实例类型（gpio/enc-mspm0）不受
  影响。

政策：
- 缺省 = 全默认：bindings 缺省或未覆盖的角色按声明默认值生成；必选角色允许
  缺省（走默认）。绑定值 == 默认值的条目保留在清单里（写侧按 no-op 跳过，
  逐字节契约不破）。
- 重复绑定不拦（同引脚多角色共享合法，spec 已定）；板外脚（如 mspm0 的
  PB4/PB5 不在排针）绑定 = 未知引脚 400。
- mspm0 槽位互斥：同一默认引脚 = 同一 syscfg 槽位（母版 $assign 引脚值唯一，
  结构测试钉），两个角色绑到不同引脚 = 冲突 400——stm32 各角色宏族独立
  （GRAY_D1 与 DIP0 同默认 PB12 但宏不同），不拦。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Sequence

from .boards import Board, board_pin, pin_capability_instances, pin_supports
from .manifest import ModuleManifest, PinDeclaration
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
        # stm32 pwm / enc / uart：类型级（ADR 0011 / ADR 0012）——实例随
        # **绑定引脚**推导喂渲染器（pwm 换实例 = 宏值变化，库零改动；enc
        # 换线 = _LINE/_EXTI 宏跟随，motor 条件 handler 自动跟随线号；uart
        # 换实例 = _UART/_INST/引脚宏跟随绑定，TX/RX 对约束在循环后统一
        # 查）；无对应 token 的脚仍拒（类型级下限）。其余平台/类型
        # strict-all：实例 = 默认引脚能力 token 的实例（板外默认如 PB4/PB5
        # 无默认引脚 → 实例空 → 只查类型）；多实例 = 全部命中（any-of 会
        # 放行 SysConfig 路由必炸的绑定——工单 02 红证已验）
        if platform == PLATFORM_STM32 and declaration.type in (
            "pwm",
            "enc",
            "uart_tx",
            "uart_rx",
        ):
            instances = pin_capability_instances(bound, declaration.type)
            if not instances:
                raise PinBindingError(
                    f"绑定 {key} 的引脚 {pin} 不支持角色类型 {declaration.type}"
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
    if platform == PLATFORM_STM32:
        _check_uart_tx_rx_pairs(board, roles, raw)
    return tuple(resolved)


def _check_uart_tx_rx_pairs(
    board: Board,
    roles: dict[tuple[str, str], PinDeclaration],
    raw: Mapping[str, str],
) -> None:
    """stm32 UART TX/RX 对同实例约束（ADR 0012 工单 02）：同一角色对（同
    slug 下 _TX/_RX 同根角色）两脚的有效实例集——绑定脚实例（已过类型级
    校验）/ 未绑默认引脚实例——交集必须非空。空 = 400 中文"必须同实例，
    请成对绑定"：单脚换实例必撞另一脚默认实例（换过去 = TX/RX 分属两
    UART，编译绿运行坏），宁严勿假绿；成对同实例 = 交集推导喂渲染器
    _UART/_INST 尾形（两脚实例同源）。只声明单脚 / 无实例（防御路径，
    真库全成对）不查。
    """
    pairs: dict[tuple[str, str], list[PinDeclaration]] = {}
    for (slug, role_id), decl in roles.items():
        if decl.type not in ("uart_tx", "uart_rx"):
            continue
        stem = role_id[:-3] if role_id.endswith(("_TX", "_RX")) else role_id
        pairs.setdefault((slug, stem), []).append(decl)

    for (slug, _), feet in pairs.items():
        tx = next(
            (d for d in feet if d.id.endswith("_TX")), None
        )
        rx = next(
            (d for d in feet if d.id.endswith("_RX")), None
        )
        if tx is None or rx is None:
            continue  # 只声明单脚的 UART 角色不查（真库全成对，防御路径）
        tx_instances = _uart_foot_instances(board, raw, slug, tx)
        rx_instances = _uart_foot_instances(board, raw, slug, rx)
        if not tx_instances or not rx_instances:
            continue  # 板外默认等无实例：不查（防御路径）
        if not (tx_instances & rx_instances):
            raise PinBindingError(
                f"绑定 {slug}.{tx.id} / {slug}.{rx.id} 的 TX/RX 必须同实例，"
                f"请成对绑定（TX 实例 {'、'.join(sorted(tx_instances))} ×"
                f" RX 实例 {'、'.join(sorted(rx_instances))} 交集为空）"
            )


def _uart_foot_instances(
    board: Board, raw: Mapping[str, str], slug: str, decl: PinDeclaration
) -> set[str]:
    """UART 角色单脚的有效实例集：绑定脚实例（raw 有值）/ 默认引脚实例。"""
    key = f"{slug}.{decl.id}"
    pin = raw.get(key)
    bound = board_pin(board, pin) if pin is not None else board_pin(board, decl.default)
    if bound is None:
        return set()
    return set(pin_capability_instances(bound, decl.type))


def _check_slot_conflicts(resolved: Sequence[ResolvedBinding]) -> None:
    """mspm0 槽位互斥：同一默认引脚 = 同一 syscfg 槽位，绑到不同引脚 = 冲突。

    判例：motor.AA 与 key.DC_MOTOR_AA 同默认 PA16（syscfg DC_MOTOR 槽位 AA
    单落点），两模块同时选中并绑到不同脚时物理互斥——400 大声失败比静默
    后者覆盖前者诚实。同默认同引脚（= 同槽位一致绑定）不拦（重复共享合法）。
    """
    by_default: dict[str, ResolvedBinding] = {}
    for binding in resolved:
        default = binding.declaration.default
        previous = by_default.get(default)
        if previous is not None and previous.pin != binding.pin:
            raise PinBindingError(
                f"绑定冲突：{previous.role_key} 与 {binding.role_key} 共用同一"
                f"槽位（默认引脚 {default}）却绑到不同引脚"
                f" {previous.pin}、{binding.pin} —— 请绑到同一引脚"
            )
        by_default[default] = binding
