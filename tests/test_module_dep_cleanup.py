"""模块依赖清理（module-dep-cleanup）：真实库数据/代码不变量。

工单 01/02 的验收：motor mspm0 纯驱动化、编码器计数归属 motor、
key 纯按键、xunji 走 motor API、依赖声明与代码一致。
"""

from pathlib import Path

from contest_generator.library import list_modules

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"


def _manifest(slug: str):
    return next(m for m in list_modules(MODULES) if m.slug == slug)


def _read(slug: str, rel: str) -> str:
    return (MODULES / slug / rel).read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# 工单 01：motor mspm0 纯驱动化
# ---------------------------------------------------------------------------


def test_motor_mspm0_source_has_no_old_project_logic():
    """motor.c 不含旧工程逻辑符号（巡线/PID/姿态/声光/OLED 自检/状态机）。"""
    motor_c = _read("motor", "code/motor.c")
    for banned in (
        "adjust_motor_pwm",
        "adjust_motor(",
        "adjust_head",
        "motor_test",
        "encoder_test",
        "pid_tuning",
        "huidu_value",
        "current_attitude",
        "OLED_",
        "led_on",
        "led_off",
        "beep_on",
        "beep_off",
        "get_time_stamp_ms",
        "gyro_frame_timeout",
        "status_change",
        "huidu_centroid",
    ):
        assert banned not in motor_c, f"motor.c 仍含旧工程逻辑符号 {banned}"


def test_motor_mspm0_header_has_only_pure_driver_includes_and_api():
    """motor.h 不 include 无关模块头；纯驱动 API + motor_encoder_read 声明。"""
    motor_h = _read("motor", "code/motor.h")
    for banned in ("huidu.h", "imu.h", "led_beep.h", "ntb_time.h"):
        assert banned not in motor_h, f"motor.h 仍 include {banned}"
    for required in (
        "void motor_init(",
        "void motor_set_duty(",
        "void motor_set_direction(",
        "int limit_duty(",
    ):
        assert required in motor_h


def test_motor_manifest_deps_empty_and_description_pure():
    """motor manifest deps 清空；简介不再声称 PID/巡线。"""
    motor = _manifest("motor")
    assert motor.dependencies == ()
    assert "PID" not in motor.description
    assert "巡线" not in motor.description


# ---------------------------------------------------------------------------
# 工单 02：编码器归属 motor + 依赖声明修正
# ---------------------------------------------------------------------------


def test_motor_owns_encoder_counters_and_irq():
    """编码器计数与 GROUP1_IRQHandler 在 motor.c，key.c 不再持有。"""
    motor_c = _read("motor", "code/motor.c")
    key_c = _read("key", "code/key.c")
    for symbol in ("uint32_t counter_1_A", "uint32_t counter_2_A", "GROUP1_IRQHandler"):
        assert symbol in motor_c, f"motor.c 缺编码器归属符号 {symbol}"
        assert symbol not in key_c, f"key.c 仍持有编码器归属符号 {symbol}"


def test_motor_exposes_encoder_read_api():
    """motor_encoder_read 声明/实现双端在场。"""
    assert "motor_encoder_read" in _read("motor", "code/motor.h")
    assert "void motor_encoder_read" in _read("motor", "code/motor.c")


def test_key_is_pure_button_and_manifest_pins_only_key():
    """key.c 只读按键；key manifest 只声明 KEY_START 引脚。"""
    key_c = _read("key", "code/key.c")
    assert "get_key_state" in key_c
    key = _manifest("key")
    mspm0 = key.platforms["mspm0"]
    assert [p.id for p in mspm0.pins] == ["KEY_START"]


def test_xunji_uses_motor_encoder_read_and_deps_motor_only():
    """xunji 走 motor API 读编码器、不 extern counter；deps 只有 motor。"""
    xunji_c = _read("xunji", "code/xunji.c")
    assert "motor_encoder_read" in xunji_c
    assert "extern uint32_t counter" not in xunji_c
    assert _manifest("xunji").dependencies == ("motor",)


def test_uwb_uart_deps_include_filter():
    """uwb_uart 真实使用 filter，manifest 补声明。"""
    uwb = _manifest("uwb_uart")
    assert set(uwb.dependencies) == {"config", "filter"}
