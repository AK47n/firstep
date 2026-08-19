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
    # 角度钳位与换算：0/180 端点
    assert "angle > 180" in stm32_c and "angle > 180" in mspm0_c


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
