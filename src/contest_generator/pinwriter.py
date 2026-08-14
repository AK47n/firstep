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

纯文本函数（字符串进、字符串出），盘上应用由 generator 挂钩（apply_pin_bindings
统一入口）——keil.py render_master_uvprojx 确定性渲染先例。写侧只吃
ResolvedBinding（pin_bindings.resolve_bindings 已校验），不再自判形状。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from .patchers import UnknownPlatformError
from .pin_bindings import PinBindingError, ResolvedBinding
from .platforms import PLATFORM_MSPM0, PLATFORM_STM32

PIN_CONFIG_FILENAME = "pin_config.h"
MSPM0_SYSCFG_FILENAME = "mspm0.syscfg"

# pin_config.h 宏行：#define NAME<分隔空白><值 + 注释>——只对绑定角色的宏行
# 整行重构（head/name/sep 原样保留 = 列对齐不动），未触碰行逐字节原样
_DEFINE_LINE_RE = re.compile(
    r"^(?P<head>\s*#\s*define\s+)(?P<name>[A-Za-z_]\w*)(?P<sep>\s+)(?P<rest>.*)$"
)

# syscfg 引脚落点行：<实例路径>.$assign = "<引脚值>"——路径含 .$assign 即
# 落点（peripheral/ccp0Pin/rxPin/txPin/sdaPin/sclPin/pin 全形态），值 = 引脚名；
# eol 单独捕获（CRLF 母版，重构时行尾原样接回——逐字节契约不破）
_SYSCFG_ASSIGN_RE = re.compile(
    r'^(?P<head>\s*.+\.\$assign\s*=\s*)"(?P<pin>[A-Za-z0-9]+)"(?P<tail>.*?)'
    r"(?P<eol>\r?\n)?$"
)


def apply_pin_bindings(
    output_dir: Path, platform: str, resolved: Sequence[ResolvedBinding]
) -> Path | None:
    """写侧统一入口（generator 在 copytree 后挂钩）：stm32 覆写 pin_config.h、
    mspm0 改写 mspm0.syscfg。文本无变化（全部绑定 = 默认值 / 未覆盖）不落盘
    返回 None——缺省路径 = 旧行为逐字节。

    未知平台抛 UnknownPlatformError（与 patchers 同缝；绑定在 stm32/mspm0
    之外无板定义，generate 入口的 board_for_platform 已先拦）。
    """
    if platform == PLATFORM_STM32:
        path = output_dir / PIN_CONFIG_FILENAME
        original = path.read_text(encoding="utf-8", newline="")
        rendered = render_pin_config(original, resolved)
    elif platform == PLATFORM_MSPM0:
        path = output_dir / MSPM0_SYSCFG_FILENAME
        original = path.read_text(encoding="utf-8", newline="")
        rendered = rewrite_syscfg(original, resolved)
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
    - `_PORT` / `_GPIO` → `GPIO_<口>`（引脚 PA6 → GPIO_A）
    - `_PIN` / `_Pin` → `Pin_<号>`（引脚 PA6 → Pin_6）

    注释里的旧引脚字样同步替换（`/* PA2，下降沿触发 */` → `/* PB2，… */`）。
    母版 pin_config.h 中没有的宏（如 ml_mpu6050 的 I2C_GPIO 住在 ml_i2c.h）
    = 数据不在此文件可控 → PinBindingError 大声失败（实践上门禁实例锁已拦，
    此路为防御）。
    """
    changes: list[ResolvedBinding] = [
        b for b in resolved if b.pin != b.declaration.default
    ]
    if not changes:
        return master_text

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
    return "".join(lines)


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
    """按绑定改写 mspm0.syscfg：按角色默认引脚值定位 $assign 落点行、只换
    引号里的引脚值——实例名 / 宏名 / 通道名 / 其余行逐字节不动。

    槽位定位 = 默认引脚值（母版 syscfg 的 $assign 引脚值唯一，结构测试钉）：
    角色声明默认值 = 地猛星化后 syscfg 现值（工单 01），逐角色找到唯一落点
    行即该角色的槽位——xunji P1-P8 与 HUIDU 槽位错序共享也天然对位（P1 默认
    PA24 → HUIDU L3 槽位）。板外默认（HUIDU R3/R4 = PB4/PB5）仍在 syscfg 有
    落点（LaunchPad 遗留值），未绑不动、绑定即换。同一槽位两角色（motor.AA
    / key.DC_MOTOR_AA）同默认 = 同落点，绑同脚合法、绑异脚在 resolve 已拦。
    """
    changes: list[ResolvedBinding] = [
        b for b in resolved if b.pin != b.declaration.default
    ]
    if not changes:
        return master_text

    lines = master_text.splitlines(keepends=True)
    sites: dict[str, list[int]] = {}
    for i, line in enumerate(lines):
        m = _SYSCFG_ASSIGN_RE.match(line)
        if m:
            sites.setdefault(m.group("pin"), []).append(i)

    by_default: dict[str, str] = {}
    for binding in changes:
        default = binding.declaration.default
        previous_pin = by_default.get(default)
        if previous_pin is not None and previous_pin != binding.pin:
            raise PinBindingError(
                f"绑定冲突：同一槽位（默认引脚 {default}）的两个角色绑到不同"
                f"引脚 {previous_pin}、{binding.pin} —— 请绑到同一引脚"
            )
        by_default[default] = binding.pin

    for default, pin in by_default.items():
        line_nos = sites.get(default) or []
        if len(line_nos) != 1:
            raise PinBindingError(
                f"角色默认引脚 {default} 在母版 {MSPM0_SYSCFG_FILENAME} 中的"
                f"落点不是唯一一行（找到 {len(line_nos)} 行）——声明"
                f"默认值与 syscfg 漂移，请核对工单 01 数据"
            )
        line_no = line_nos[0]
        m = _SYSCFG_ASSIGN_RE.match(lines[line_no])
        assert m is not None  # sites 收录时已匹配过
        lines[line_no] = (
            f'{m.group("head")}"{pin}"{m.group("tail")}{m.group("eol") or ""}'
        )
    return "".join(lines)
