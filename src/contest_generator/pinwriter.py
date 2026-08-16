"""板级引脚绑定写侧（工单 02）：stm32 pin_config.h 确定性渲染 + mspm0 syscfg 改写。

契约（spec 板级引脚配置）：
- 默认绑定（bindings 缺省 / 未覆盖角色 / 绑定值 = 默认值）输出与母版
  **逐字节一致**——实现上"不变不写"：变换先算文本、与原文本逐字相等即不
  落盘；母版两文件是 CRLF，读/写走 newline="" 原样保留行尾。
- 绑定改哪几个角色，只变对应宏行（stm32）/ 只换 $assign 引脚值（mspm0）——
  行级替换，其余行原样保留。
- mspm0 只碰 `$assign` 引号值：实例名 / 宏名 / 通道名不动（通道名有
  DCC_100_PWM2 先例：ti_driverlib_pwm_DCC100_CC0 为避与 PWMAB 重名改名过，
  改写器碰它必炸 SysConfig）。
- 共享端口宏异值 400（ADR 0011 工单 02）：同 `_GPIO/_PORT` 尾形宏的两条改动
  绑定计算值不同 → PinBindingError（SCL/SDA 须同口）；只查改动项，未改同族
  角色的隐式漂移仍为提示语义（前端卡片已做）。

纯文本函数（字符串进、字符串出），盘上应用由 generator 挂钩（apply_pin_bindings
统一入口）——keil.py render_master_uvprojx 确定性渲染先例。写侧只吃
ResolvedBinding（pin_bindings.resolve_bindings 已校验），不再自判形状。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Sequence

from .patchers import UnknownPlatformError
from .pin_bindings import PinBindingError, ResolvedBinding
from .platforms import PLATFORM_MSPM0, PLATFORM_STM32
from .syscfg_model import MSPM0_SYSCFG_FILENAME, SyscfgModelError, parse_syscfg

PIN_CONFIG_FILENAME = "pin_config.h"

# USART 聚合宏（母版 pin_config.h / isr.c 三对同源）：宏名 ↔ 实例（USART1
# ↔ UART_1）。渲染器按 {STEM}_UART 宏现值重分组（绑定换实例 → 宏值变 →
# CALLS 跟随），数据源唯一。
_IRQ_CALLS_MACROS = (
    "USART1_IRQ_CALLS",
    "USART2_IRQ_CALLS",
    "USART3_IRQ_CALLS",
)

# UART 角色宏根 → rx_handler 函数名（默认分组序 + isr.c __weak 兜底名同源；
# zigbee_uart_key 与 zigbee_uart 共享 ZIGBEE_* 宏，handler 只列一次）。
_UART_CALLS_ROLES = (
    ("DIGIT_UART", "digit_uart_rx_handler"),
    ("COORD_DETECT_UART", "coord_detect_rx_handler"),
    ("DEBUG_UART", "debug_uart_rx_handler"),
    ("UWB_UART", "uwb_rx_handler"),
    ("ZIGBEE_UART", "zigbee_rx_handler"),
)

# pin_config.h 宏行：#define NAME<分隔空白><值 + 注释>——只对绑定角色的宏行
# 整行重构（head/name/sep 原样保留 = 列对齐不动），未触碰行逐字节原样
_DEFINE_LINE_RE = re.compile(
    r"^(?P<head>\s*#\s*define\s+)(?P<name>[A-Za-z_]\w*)(?P<sep>\s+)(?P<rest>.*)$"
)

def apply_pin_bindings(
    output_dir: Path,
    platform: str,
    resolved: Sequence[ResolvedBinding],
    *,
    selected_slugs: Iterable[str],
) -> Path | None:
    """写侧统一入口（generator 在 copytree 后挂钩）：stm32 覆写 pin_config.h、
    mspm0 改写 mspm0.syscfg。

    mspm0 走单一 pipeline（工单 syscfg-file-model/04）：读 syscfg 一次解析 →
    prune(selected_slugs) → rewrite(resolved) → serialize——先后由构造保证，
    不再靠调用顺序/注释；selected_slugs 只 mspm0 用（未选模块实例不落盘，
    其引脚空出来可绑；必传，缺省会静默全裁故不设默认）。文本无变化（全默认 /
    未覆盖 / 全选理论模块）不落盘返回 None——缺省路径 = 旧行为逐字节。

    未知平台抛 UnknownPlatformError（与 patchers 同缝；绑定在 stm32/mspm0
    之外无板定义，generate 入口的 board_for_platform 已先拦）。
    """
    if platform == PLATFORM_STM32:
        path = output_dir / PIN_CONFIG_FILENAME
        original = path.read_text(encoding="utf-8", newline="")
        rendered = render_pin_config(original, resolved)
    elif platform == PLATFORM_MSPM0:
        path = output_dir / MSPM0_SYSCFG_FILENAME
        if not path.is_file():
            return None  # 假母版/测试树可能无 syscfg；真母版必有，防御跳过
        original = path.read_text(encoding="utf-8", newline="")
        try:
            rendered = (
                parse_syscfg(original)
                .prune(selected_slugs)
                .rewrite(resolved)
                .to_text()
            )
        except SyscfgModelError as exc:
            raise PinBindingError(str(exc)) from exc
    else:
        raise UnknownPlatformError(
            f"未知平台 {platform!r}，已注册的平台：{PLATFORM_STM32}, {PLATFORM_MSPM0}"
        )
    if rendered == original:
        return None  # 无生效绑定：不写盘（逐字节契约由"不变不写"兜底）
    path.write_text(rendered, encoding="utf-8", newline="")
    return path


def render_pin_config(
    master_text: str, resolved: Sequence[ResolvedBinding]
) -> str:
    """按绑定渲染 pin_config.h 全文：绑定角色的宏行换值（行级替换），其余行
    逐字节保留。绑定值 = 默认值的角色 = no-op（跳过，不碰任何行）。

    宏值形状（按宏名尾形分派，母版现值即这些形状）：
    - `_EXTI` → `EXTI_<引脚>`（ml_exti 枚举 = 引脚名）
    - `_LINE` → 编码器线号（实例 = enc:N 的 N；EXTI handler 名绑线号，门禁
      已限同线号引脚，线号不变）
    - `_TIM` → `TIM_<N>`（ml_pwm 定时器枚举，实例 TIM2_CH1 → TIM_2）
    - `_CH` → 通道枚举（= 实例 token 原样，如 TIM2_CH1）
    - `_UART` → UART 实例枚举（= 实例原样，如 UART_1）
    - `_INST` → 寄存器外设宏（USART<N>，实例 UART_1 → USART1）
    - `_PORT` / `_GPIO` → `GPIO_<口>`（引脚 PA6 → GPIO_A；uart 引脚宏
      `_TX_GPIO`/`_RX_GPIO` 同此尾形）
    - `_PIN` / `_Pin` → `Pin_<号>`（引脚 PA6 → Pin_6；uart 引脚宏
      `_TX_Pin`/`_RX_Pin` 同此尾形）
    - `_IRQ_CALLS` → 不在角色宏清单里：独立重分组通道（见
      `_regroup_irq_calls`——按各 {STEM}_UART 宏现值把 rx_handler 调用归入
      USARTx_IRQ_CALLS，绑定换实例即重排）。

    注释里的旧引脚字样同步替换（`/* PA2，下降沿触发 */` → `/* PB2，… */`）。
    母版 pin_config.h 中没有的宏 = 数据不在此文件可控 → PinBindingError 大声
    失败（软 I2C 宏随工单 02 迁入本文件后此路真机不可达，防御路径）。共享
    端口宏异值冲突（两条改动写同一 `_GPIO/_PORT` 宏且值不同）在写行前拦。
    """
    changes: list[ResolvedBinding] = [
        b for b in resolved if b.pin != b.declaration.default
    ]
    if not changes:
        return master_text

    _check_shared_port_macro_conflicts(changes)

    lines = master_text.splitlines(keepends=True)
    index: dict[str, int] = {}
    for i, line in enumerate(lines):
        m = _DEFINE_LINE_RE.match(line)
        if m:
            index[m.group("name")] = i

    for binding in changes:
        for macro in binding.declaration.macros:
            if macro not in index:
                raise PinBindingError(
                    f"绑定 {binding.role_key} 需要改写宏 {macro}，但母版 "
                    f"{PIN_CONFIG_FILENAME} 中没有该宏（stm32 v1 只支持本文件"
                    f"内的宏——ml_libs 内部写死实例属第二层锁，spec 已留痕）"
                )
            line_no = index[macro]
            new_line = _replace_define_line(
                lines[line_no],
                macro,
                _stm32_macro_value(
                    binding.role_key, macro, binding.pin, binding.instances
                ),
                old_pin=binding.declaration.default,
                new_pin=binding.pin,
            )
            if new_line != lines[line_no]:
                lines[line_no] = new_line

    if any(b.declaration.type in ("uart_tx", "uart_rx") for b in changes):
        _regroup_irq_calls(lines, index)  # CALLS 按 {STEM}_UART 现值重分组
    return "".join(lines)


def _regroup_irq_calls(lines: list[str], index: dict[str, int]) -> None:
    """USARTx_IRQ_CALLS 行重分组（ADR 0012 工单 02）：按各 UART 角色
    {STEM}_UART 宏的**现值**（绑定换实例后的新值）把 rx_handler 调用归入
    对应 USARTx_IRQ_CALLS——组跟宏走（共享宏隐式漂移天然跟随），未变角色
    保留默认分组；重分组后与现值逐字相同的行不写（非 uart 绑定不碰 CALLS
    行，逐字节契约不破）。宏值不在 UART_1/2/3 = 数据漂移，大声失败。
    """
    groups: dict[str, list[str]] = {macro: [] for macro in _IRQ_CALLS_MACROS}
    for stem, handler in _UART_CALLS_ROLES:
        line = lines[index[stem]]
        m = _DEFINE_LINE_RE.match(line)
        assert m is not None, f"母版 {PIN_CONFIG_FILENAME} 缺宏 {stem}"
        value = m.group("rest").strip().split(None, 1)[0]
        if value not in ("UART_1", "UART_2", "UART_3"):
            raise PinBindingError(
                f"无法按 {stem} 宏值 {value!r} 分组 IRQ 调用——USARTx_IRQ_CALLS"
                f" 重分组只认 UART_1/2/3（母版数据漂移）"
            )
        groups["USART" + _digits(value) + "_IRQ_CALLS"].append(handler + "()")

    for macro in _IRQ_CALLS_MACROS:
        line = lines[index[macro]]
        m = _DEFINE_LINE_RE.match(line)
        assert m is not None, f"母版 {PIN_CONFIG_FILENAME} 缺宏 {macro}"
        new_value = "; ".join(groups[macro]) + ";"
        rest = m.group("rest")
        if new_value == rest.strip():
            continue  # 现值一致：不写行（逐字节契约）
        # 行尾原样接回：`.*$` 会把 CRLF 的 \r 吃进 rest（_replace_define_line
        # 靠 new_rest 原样保留 \r），本通道自建值不含 \r——按母版行尾还原
        eol = "\r\n" if rest.endswith("\r") else "\n"
        lines[index[macro]] = (
            f"{m.group('head')}{macro}{m.group('sep')}{new_value}{eol}"
        )


def _check_shared_port_macro_conflicts(
    changes: Sequence[ResolvedBinding],
) -> None:
    """共享端口宏异值门禁（ADR 0011）：两条改动绑定写同一 `_GPIO/_PORT` 尾形
    宏且计算值不同（如 MPU6050_SCL→PA5、MPU6050_SDA→PB6 都写 I2C_GPIO 但值
    GPIO_A/GPIO_B 不同——一根 SCL/SDA 总线不可分属两个端口）→ PinBindingError
    400。只查改动项（未改同族角色的隐式漂移仍为提示语义，前端卡片已做）；
    同值（同端口）放行。旧"宏不在 pin_config.h 大声失败"防御保留在写行循环。"""
    by_macro: dict[str, tuple[str, str]] = {}
    for binding in changes:
        for macro in binding.declaration.macros:
            if not macro.endswith(("_GPIO", "_PORT")):
                continue
            value = _stm32_macro_value(
                binding.role_key, macro, binding.pin, binding.instances
            )
            previous = by_macro.get(macro)
            if previous is not None and previous[1] != value:
                raise PinBindingError(
                    f"共享端口宏 {macro} 被 {previous[0]}、{binding.role_key} "
                    f"绑到不同端口 {previous[1]}、{value} —— 同一总线须绑到"
                    f"同一端口（如 SCL/SDA 同 GPIO 口）"
                )
            if previous is None:
                by_macro[macro] = (binding.role_key, value)


def _stm32_macro_value(
    role_key: str, macro: str, pin: str, instances: tuple[str, ...]
) -> str:
    """宏名尾形 → 新值（形状表见 render_pin_config docstring）。"""
    if macro.endswith("_EXTI"):
        return "EXTI_" + pin
    if macro.endswith("_LINE"):
        return _require_instance(role_key, macro, instances)
    if macro.endswith("_TIM"):
        return _timer_enum(_require_instance(role_key, macro, instances))
    if macro.endswith("_CH"):
        return _require_instance(role_key, macro, instances)
    if macro.endswith("_INST"):
        return "USART" + _digits(_require_instance(role_key, macro, instances))
    if macro.endswith("_UART"):
        return _require_instance(role_key, macro, instances)
    if macro.endswith("_PORT") or macro.endswith("_GPIO"):
        return "GPIO_" + pin[1]
    if macro.endswith("_PIN") or macro.endswith("_Pin"):
        return "Pin_" + _digits(pin)
    raise PinBindingError(
        f"无法推导宏 {macro} 的引脚值形状（{role_key}）——stm32 渲染器支持"
        f" 8 种宏名尾形（_EXTI/_LINE/_TIM/_CH/_UART/_INST/_PORT/_GPIO/_PIN）"
    )


def _require_instance(role_key: str, macro: str, instances: tuple[str, ...]) -> str:
    """实例推导宏（_TIM/_CH/_UART/_INST/_LINE）需要单实例；多实例 = 默认引脚
    有多个同类型能力，渲染器无法判定用哪个——数据歧义大声失败。"""
    if len(instances) != 1:
        raise PinBindingError(
            f"角色 {role_key} 的实例歧义 {instances or '（无）'}，无法推导宏"
            f" {macro} 的值（stm32 渲染器需要默认引脚单实例）"
        )
    return instances[0]


def _timer_enum(instance: str) -> str:
    """通道实例 token → ml_pwm 定时器枚举：TIM2_CH1 → TIM_2（字母与数字间
    加下划线，ml_pwm 的 TIM_2/TIM_3/TIM_4 枚举形态）。"""
    base = instance.split("_", 1)[0]
    return re.sub(r"([A-Za-z]+)(\d+)$", r"\1_\2", base)


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def _replace_define_line(
    line: str, macro: str, new_value: str, old_pin: str, new_pin: str
) -> str:
    """单条宏行重构：head/name/sep 原样保留（列对齐不动），rest 里值 token
    换新值、注释里旧引脚字样同步替换。"""
    m = _DEFINE_LINE_RE.match(line)
    if m is None or m.group("name") != macro:
        raise PinBindingError(f"pin_config.h 宏行解析失败：{macro}")
    rest = m.group("rest")
    tokens = rest.split(None, 1)
    if not tokens:
        raise PinBindingError(f"pin_config.h 宏 {macro} 的行没有值")
    old_value = tokens[0]
    new_rest = rest.replace(old_value, new_value, 1)
    if old_pin != new_pin:
        new_rest = new_rest.replace(old_pin, new_pin)
    eol = line[m.end() :]  # 行尾原样保留（CRLF 母版，逐字节契约不破）
    return f"{m.group('head')}{m.group('name')}{m.group('sep')}{new_rest}{eol}"


def rewrite_syscfg(
    master_text: str, resolved: Sequence[ResolvedBinding]
) -> str:
    """按绑定改写 mspm0.syscfg（工单 syscfg-file-model/03）：委托文件模型
    `parse_syscfg(master_text).rewrite(resolved).to_text()`。文件模型独占
    $assign 文法、路径匹配与槽位身份（工单 01），写侧只翻译错误契约——
    SyscfgModelError 是白名单、漏到 web 层会 500，翻译回 PinBindingError
    保持旧写侧错误契约不变（消息文案与旧实现逐字一致）。"""
    try:
        return parse_syscfg(master_text).rewrite(resolved).to_text()
    except SyscfgModelError as exc:
        raise PinBindingError(str(exc)) from exc
