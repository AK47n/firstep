"""servo 模块（b1-adc-servo/02）：双平台 API 对偶 + 母版接线 + pwm 类型级绑定。

红证：servo 绑定 = pwm 类型级（现成机制）——stm32 宏值（TIM/通道随绑定
引脚推导）、mspm0 syscfg 的 ccp0Pin.$assign + peripheral 行连带改写。
"""

import re
from pathlib import Path

import pytest

from contest_generator.boards import BOARDS_DIR, load_boards
from contest_generator.library import list_modules
from contest_generator.pin_bindings import PinBindingError, resolve_bindings
from contest_generator.pinwriter import (
    PIN_CONFIG_FILENAME,
    render_pin_config,
    rewrite_syscfg,
)
from contest_generator.syscfg_model import MSPM0_SYSCFG_FILENAME, parse_syscfg

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
LIBRARY_MODULES = LIBRARY_ROOT / "modules"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"

BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}
ALL_MANIFESTS = list_modules(LIBRARY_MODULES)
SERVO_MANIFEST = next(m for m in ALL_MANIFESTS if m.slug == "servo")


def _read(rel: str) -> str:
    return (LIBRARY_ROOT / rel).read_text(encoding="utf-8", errors="replace")


def _resolve(platform: str, bindings: dict[str, str]):
    return resolve_bindings(ALL_MANIFESTS, platform, BOARDS[platform], bindings)


# ---------------------------------------------------------------------------
# manifest 形状
# ---------------------------------------------------------------------------


def test_servo_manifest_loaded_and_capability_direction():
    assert SERVO_MANIFEST.slug == "servo"
    assert "舵机" in SERVO_MANIFEST.description  # 能力方向声明
    assert "202" not in SERVO_MANIFEST.description  # 无题绑定（题号/年份）
    assert SERVO_MANIFEST.dependencies == ()


def test_servo_pins_declared_both_platforms():
    stm32 = SERVO_MANIFEST.platforms["stm32"]
    mspm0 = SERVO_MANIFEST.platforms["mspm0"]
    assert [p.id for p in stm32.pins] == ["SERVO_PWM_C0"]
    assert [p.id for p in mspm0.pins] == ["SERVO_PWM_C0"]
    assert stm32.pins[0].type == "pwm" and mspm0.pins[0].type == "pwm"
    # stm32 宏名尾形 _TIM/_CH（渲染器分派）
    assert stm32.pins[0].macros == ("SERVO_PWM_TIM", "SERVO_PWM_CH")


# ---------------------------------------------------------------------------
# 双平台 API 对偶
# ---------------------------------------------------------------------------


def test_servo_api_parity_both_platforms():
    shared_h = _read("modules/servo/code/servo.h")
    stm32_c = _read("modules/servo/code/servo_stm32.c")
    mspm0_c = _read("modules/servo/code/servo_mspm0.c")
    assert "void servo_init(uint8_t servo_id, uint8_t channel);" in shared_h
    assert "void servo_init(uint8_t servo_id, uint8_t channel)" in stm32_c
    assert "void servo_init(uint8_t servo_id, uint8_t channel)" in mspm0_c
    assert "void servo_set_angle(uint8_t servo_id, uint16_t angle);" in shared_h
    assert "servo_set_angle" in stm32_c and "servo_set_angle" in mspm0_c
    # 角度钳位：两侧都按 servo.h 的 SERVO_ANGLE_MAX 钳位（常量单源，见下条测试）
    assert "angle > SERVO_ANGLE_MAX" in stm32_c and "angle > SERVO_ANGLE_MAX" in mspm0_c


# ---------------------------------------------------------------------------
# 角度换算常量单源 + 占空比边界（工单 b1-adc-servo/02 在途盘点补口）
# ---------------------------------------------------------------------------


def _servo_constants() -> dict[str, int]:
    """从 servo.h 解析换算常量（单源出处），period/span 由频率与端点推导。"""
    text = _read("modules/servo/code/servo.h")
    values: dict[str, int] = {}
    for name in ("SERVO_FREQ_HZ", "SERVO_ANGLE_MAX", "SERVO_MIN_PULSE_US", "SERVO_MAX_PULSE_US"):
        match = re.search(rf"#define\s+{name}\s+(\d+)u?\b", text)
        assert match, f"servo.h 缺换算常量 {name}"
        values[name] = int(match.group(1))
    values["SERVO_PERIOD_US"] = 1_000_000 // values["SERVO_FREQ_HZ"]
    values["SERVO_PULSE_SPAN_US"] = values["SERVO_MAX_PULSE_US"] - values["SERVO_MIN_PULSE_US"]
    return values


def _pulse_us(consts: dict[str, int], angle: int) -> int:
    """SERVO_PULSE_US(angle) 的等价整数运算（分子一次算完再除）。"""
    return (
        consts["SERVO_MIN_PULSE_US"] * consts["SERVO_ANGLE_MAX"]
        + angle * consts["SERVO_PULSE_SPAN_US"]
    ) // consts["SERVO_ANGLE_MAX"]


def test_servo_angle_constants_single_source_in_header():
    """换算常量只在 servo.h 出现；两个 .c 引用宏、不硬编码数值。"""
    consts = _servo_constants()
    assert consts == {
        "SERVO_FREQ_HZ": 50,
        "SERVO_ANGLE_MAX": 180,
        "SERVO_MIN_PULSE_US": 500,
        "SERVO_MAX_PULSE_US": 2500,
        "SERVO_PERIOD_US": 20000,
        "SERVO_PULSE_SPAN_US": 2000,
    }
    for rel in ("modules/servo/code/servo_stm32.c", "modules/servo/code/servo_mspm0.c"):
        text = _read(rel)
        assert "SERVO_PULSE_US(" in text, f"{rel} 未使用单源换算宏"
        assert "SERVO_PERIOD_US" in text, f"{rel} 未使用单源周期常量"
        assert "SERVO_ANGLE_MAX" in text, f"{rel} 未使用单源角度满量程"
        # 硬编码回归：换算常量不得再散落在平台 .c 里
        for literal in ("1250", "5000 /", "/ 1800", "/ 40", "> 180"):
            assert literal not in text, f"{rel} 仍硬编码换算常量片段 {literal!r}"


def test_servo_duty_boundaries_stm32():
    """stm32：0/90/180° → MAX_DUTY 满量程下的计数值 1250 / 3750 / 6250。"""
    consts = _servo_constants()
    pwm_h = (STM32_MASTER / "ml_libs" / "ml_pwm.h").read_text(encoding="utf-8", errors="replace")
    max_duty = int(re.search(r"#define\s+MAX_DUTY\s+(\d+)", pwm_h).group(1))
    duty = {angle: max_duty * _pulse_us(consts, angle) // consts["SERVO_PERIOD_US"] for angle in (0, 90, 180)}
    assert duty == {0: 1250, 90: 3750, 180: 6250}
    # 脉宽语义核对：0.5ms / 1.5ms / 2.5ms（MAX_DUTY 对应 20ms）
    assert duty[0] * consts["SERVO_PERIOD_US"] // max_duty == 500
    assert duty[180] * consts["SERVO_PERIOD_US"] // max_duty == 2500


def test_servo_duty_boundaries_mspm0():
    """mspm0：占空比 = 周期 × 脉宽 / 周期us，0/90/180° 落在 0.5/1.5/2.5ms。"""
    consts = _servo_constants()
    for period in (640_000, 1_600_000):  # 32MHz / 80MHz 下的 20ms 计数值
        duty = {angle: period * _pulse_us(consts, angle) // consts["SERVO_PERIOD_US"] for angle in (0, 90, 180)}
        for angle, expected_us in ((0, 500), (90, 1500), (180, 2500)):
            # 计数值 → 微秒：duty / period × 20000us
            assert abs(duty[angle] * consts["SERVO_PERIOD_US"] // period - expected_us) <= 1, (period, angle, duty)


# ---------------------------------------------------------------------------
# 母版接线
# ---------------------------------------------------------------------------


def test_stm32_master_has_servo_macros():
    text = (STM32_MASTER / PIN_CONFIG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    assert re.search(r"#define\s+SERVO_PWM_TIM\s+TIM_4\b", text)
    assert re.search(r"#define\s+SERVO_PWM_CH\s+TIM4_CH1\b", text)


def test_mspm0_master_syscfg_has_servo_pwm_instance():
    text = (MSPM0_MASTER / MSPM0_SYSCFG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    model = parse_syscfg(text)
    assert "SERVO_PWM" in model.instances
    assert re.search(r"SERVO_PWM\.peripheral\.\$assign\s*=\s*\"TIMG8\"", text)
    assert re.search(r"SERVO_PWM\.peripheral\.ccp0Pin\.\$assign\s*=\s*\"PA7\"", text)


# ---------------------------------------------------------------------------
# 绑定（pwm 类型级现成机制）
# ---------------------------------------------------------------------------


def test_stm32_servo_binding_rewrites_macros():
    master = (STM32_MASTER / PIN_CONFIG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    # PB6(TIM4_CH1) → PA0(TIM2_CH1)
    resolved = _resolve("stm32", {"servo.SERVO_PWM_C0": "PA0"})
    assert resolved[0].instances == ("TIM2_CH1",)
    rendered = render_pin_config(master, resolved)
    assert re.search(r"#define\s+SERVO_PWM_TIM\s+TIM_2\b", rendered)
    assert re.search(r"#define\s+SERVO_PWM_CH\s+TIM2_CH1\b", rendered)


def test_stm32_servo_binding_rejects_non_pwm_pin():
    with pytest.raises(PinBindingError):
        _resolve("stm32", {"servo.SERVO_PWM_C0": "PB12"})


def test_mspm0_servo_binding_rewrites_peripheral_and_pin():
    master = (MSPM0_MASTER / MSPM0_SYSCFG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    # PA7(TIMG8_C0) → PA12(TIMG0_C0)：peripheral 行 + ccp0Pin 行连带改写
    resolved = _resolve("mspm0", {"servo.SERVO_PWM_C0": "PA12"})
    rewritten = rewrite_syscfg(master, resolved)
    assert re.search(r"SERVO_PWM\.peripheral\.\$assign\s*=\s*\"TIMG0\"", rewritten)
    assert re.search(r"SERVO_PWM\.peripheral\.ccp0Pin\.\$assign\s*=\s*\"PA12\"", rewritten)


def test_mspm0_servo_binding_same_pin_is_noop():
    master = (MSPM0_MASTER / MSPM0_SYSCFG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    resolved = _resolve("mspm0", {"servo.SERVO_PWM_C0": "PA7"})  # = 默认值
    assert rewrite_syscfg(master, resolved) == master


# ---------------------------------------------------------------------------
# 骨架接口块
# ---------------------------------------------------------------------------


def test_servo_interfaces_available_to_skeleton():
    from contest_generator.skeleton import build_skeleton_interfaces

    for platform, master in (("stm32", STM32_MASTER), ("mspm0", MSPM0_MASTER)):
        blocks = build_skeleton_interfaces(
            [SERVO_MANIFEST], platform, LIBRARY_MODULES, master
        )
        joined = "\n".join(blocks)
        assert "servo.h" in joined
        assert "servo_init" in joined and "servo_set_angle" in joined
