"""引脚绑定：载荷解析与校验（板级引脚配置工单 02 机制层）。

bindings 载荷 = `{"<slug>.<role_id>": "<PIN>"}`（spec 板级引脚配置）——本模块
是绑定的唯一校验出口：角色存在于选中模块声明（manifest pins）、引脚存在于
板定义排针（boards.board_pin）、能力合法（boards.pin_supports；角色实例 =
默认引脚能力 token 的实例，boards.pin_capability_instances 推导——enc 限同
EXTI 线号的机械实现）。校验通过产出 ResolvedBinding——写侧渲染器 / 改写器
只吃已解析结构，不再自判形状（工单 02 文件边界：模型归本模块）。

能力口径（strict-all）：绑定引脚须支持默认引脚的**全部**实例——mspm0 复用
标注多实例引脚（motor.PWMAB_C0 默认 PA12 有 pwm:TIMG0_C0 + pwm:TIMA0_C3）
只有同双实例的引脚才可绑（现状仅 PA12 自身 = 锁死）。宁严勿假绿：syscfg
改写器只换 $assign 不改外设（PWMAB.peripheral = TIMG0 不动），绑到只有
TIMA0_C3 的脚（如 PA28）会让 SysConfig 路由失败——strict-all 把这类"界面
显示兼容但构建必炸"的绑定挡在生成前。单实例类型（uart/i2c/enc/stm32 pwm）
与无实例类型（gpio/enc-mspm0）不受影响。

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
from .platforms import PLATFORM_MSPM0


class PinBindingError(ValueError):
    """引脚绑定载荷非法（键格式 / 未知角色 / 未知引脚 / 能力不符 / 槽位冲突）。"""


@dataclass(frozen=True)
class ResolvedBinding:
    """一条通过校验的绑定：写侧只吃它（渲染器 / 改写器不再自判形状）。

    instances = 角色实例（默认引脚能力 token 的实例，pin_capability_instances
    推导；gpio_out/gpio_in 与 mspm0 enc 等无实例类型为空元组）。stm32 渲染器
    需要单实例推导宏值（多实例 = 数据歧义，渲染处大声失败）。
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
    引脚在板定义排针（板外脚 = 未知引脚）/ 能力合法（strict-all：绑定引脚
    须支持默认引脚能力 token 的**全部**实例——mspm0 复用标注多实例引脚的
    先例：motor.PWMAB_C0 默认 PA12 有 pwm:TIMG0_C0 + pwm:TIMA0_C3，仅
    TIMA0_C3 的脚如 PA28 会让 SysConfig 路由失败，宁严勿假绿）。mspm0 同默认
    引脚两角色绑不同脚 = 槽位冲突互斥（syscfg 单落点）。顺序 = 载荷插入
    顺序（dict 保序，写侧覆盖顺序确定性）。
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
        # 角色实例 = 默认引脚能力 token 的实例（板外默认如 PB4/PB5 无默认
        # 引脚 → 实例空 → 只查类型）；多实例 = 全部命中（strict-all，
        # any-of 会放行 SysConfig 路由必炸的绑定——工单 02 红证已验）
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
    return tuple(resolved)


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
