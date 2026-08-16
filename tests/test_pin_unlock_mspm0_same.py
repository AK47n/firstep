"""mspm0 同族实例迁移 Tier A（工单 pin-full-unlock/03，ADR 0012）：uart/i2c
类型级 + 成对同实例约束（平台通用）+ UART 实例冲突门禁（mspm0 同口径）+
pwm 同族内类型级 + step_motor 同端口门禁 + syscfg 改写器 peripheral 行。

契约：默认绑定输出与母版逐字节一致；uart/i2c/pwm 换脚 → syscfg 引脚 $assign
与 peripheral $assign 联动改写，实例名 / 宏名 / 通道名不动；gpio 组不需要
port 字段（SysConfig 由组内引脚自动推导 STEP_MOTOR_PORT，前置验证 2026-08-15
实证）。红证 = resolve / 门禁每个拒绝分支；绿证 = 产物字段断言 + 默认逐字节。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.boards import BOARDS_DIR, load_boards
from contest_generator.errors import error_entry
from contest_generator.generator import (
    GateContext,
    ModuleCorpus,
    UartInstanceConflictError,
    _check_uart_instance_conflicts,
)
from contest_generator.library import list_modules
from contest_generator.pin_bindings import PinBindingError, resolve_bindings
from contest_generator.pinwriter import rewrite_syscfg
from contest_generator.syscfg_model import MSPM0_SYSCFG_FILENAME

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
LIBRARY_MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"

BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}
ALL_MANIFESTS = list_modules(LIBRARY_MODULES)
MSPM0_MASTER_SYSCFG = (MSPM0_MASTER / MSPM0_SYSCFG_FILENAME).read_text(
    encoding="utf-8", newline=""
)

# mspm0 UART 换位（真机场景 ② 同款）：IMU601 UART0→UART1（PA8/PA9）、
# DIGIT_UART UART1→UART0（PA28/PA31）、ball_detect 与 DIGIT_UART 共享实例
# 一并成对换到 UART0——绑定×绑定，实例冲突门禁放行。
UART_SWAP_BINDINGS = {
    "imu_uart.IMU601_TX": "PA8",
    "imu_uart.IMU601_RX": "PA9",
    "digit_uart.DIGIT_UART_TX": "PA28",
    "digit_uart.DIGIT_UART_RX": "PA31",
    "ball_detect.BALL_DETECT_UART_TX": "PA28",
    "ball_detect.BALL_DETECT_UART_RX": "PA31",
}


def _resolve(bindings: dict[str, str]):
    return resolve_bindings(ALL_MANIFESTS, "mspm0", BOARDS["mspm0"], bindings)


def _corpus(main_c: str = "") -> ModuleCorpus:
    return ModuleCorpus(
        platform="mspm0",
        modules=(),
        missing_platforms=(),
        missing_files=(),
        master_headers=(),
        master_search_dirs=(),
        search_dir_headers=(),
        master_project_dir=Path("."),
        main_c=main_c,
    )


def _uart_conflict_check(bindings: dict[str, str]):
    _check_uart_instance_conflicts(
        _corpus(), ALL_MANIFESTS, "mspm0",
        GateContext(bindings=bindings, board=BOARDS["mspm0"]),
    )


# ---------------------------------------------------------------------------
# resolve：mspm0 uart / i2c 类型级 + 成对同实例
# ---------------------------------------------------------------------------


def test_resolve_mspm0_uart_type_level_pair_to_uart1():
    """uart 类型级（ADR 0012 工单 03）：实例随绑定引脚推导——IMU601 成对绑
    PA8/PA9（UART1）→ 两脚实例 ("UART1",)（旧实例锁：默认 UART0 只认
    PA28/PA31）。"""
    resolved = _resolve(
        {"imu_uart.IMU601_TX": "PA8", "imu_uart.IMU601_RX": "PA9"}
    )
    assert {b.role_key: b.instances for b in resolved} == {
        "imu_uart.IMU601_TX": ("UART1",),
        "imu_uart.IMU601_RX": ("UART1",),
    }


def test_resolve_mspm0_uart_pair_intersection_empty_400():
    """TX/RX 对同实例约束（平台通用）：IMU601 TX→PA8（UART1）× RX→PA31
    （UART0）交集空 → 400 中文"必须同实例，请成对绑定"。"""
    with pytest.raises(PinBindingError, match="必须同实例，请成对绑定") as excinfo:
        _resolve({"imu_uart.IMU601_TX": "PA8", "imu_uart.IMU601_RX": "PA31"})
    assert "IMU601_TX" in str(excinfo.value)
    assert "IMU601_RX" in str(excinfo.value)


def test_resolve_mspm0_i2c_type_level_and_pair_constraint():
    """i2c 类型级 + SCL/SDA 成对同实例：OLED SCL→PA17（I2C1）合法（SDA 默认
    PB3 同 I2C1）；SCL→PA17（I2C1）× SDA→PA0（I2C0）交集空 → 400。"""
    resolved = _resolve({"oled.OLED_SCL": "PA17"})
    assert resolved[0].instances == ("I2C1",)
    with pytest.raises(PinBindingError, match="SCL/SDA 必须同实例"):
        _resolve({"oled.OLED_SCL": "PA17", "oled.OLED_SDA": "PA0"})


def test_resolve_mspm0_pwm_channel_still_enforced():
    """03 的族锁在 04 拆掉后，通道匹配仍是类型级下限：PWMAB_C0 → PB18
    （TIMA0_C2N / TIMA1_C1 均非 C0）→ 400；跨族合法路径（PA8）由
    tests/test_pin_unlock_mspm0_cross.py 覆盖。"""
    with pytest.raises(PinBindingError, match="pwm 通道 C0"):
        _resolve({"motor.PWMAB_C0": "PB18"})


def test_resolve_mspm0_step_motor_same_port_gate():
    """step_motor 四脚同端口门禁：只绑 RST2→PA15（其余默认 PB）→ 400 中文；
    四脚全绑 PA15/PA16/PA17/PA18 同端口 → 放行。"""
    with pytest.raises(PinBindingError, match="必须绑到同一端口"):
        _resolve({"step_motor.STEP_MOTOR_RST2": "PA15"})
    resolved = _resolve(
        {
            "step_motor.STEP_MOTOR_RST2": "PA15",
            "step_motor.STEP_MOTOR_SLP2": "PA16",
            "step_motor.STEP_MOTOR_DIR2": "PA17",
            "step_motor.STEP_MOTOR_DCY2": "PA18",
        }
    )
    assert len(resolved) == 4


# ---------------------------------------------------------------------------
# UART 实例冲突门禁（mspm0 同口径）
# ---------------------------------------------------------------------------


def test_uart_instance_conflict_gate_mspm0_single_role_move_rejected():
    """IMU601 单方面换 UART1 撞未绑 ball_detect（与 digit_uart 共享
    DIGIT_UART）默认 UART1 → 400 中文（生成前拦；SysConfig Resource
    conflict 已验证同语义）。"""
    with pytest.raises(UartInstanceConflictError, match="默认实例 UART1") as excinfo:
        _uart_conflict_check(
            {"imu_uart.IMU601_TX": "PA8", "imu_uart.IMU601_RX": "PA9"}
        )
    assert "IMU601_TX" in str(excinfo.value)
    assert "BALL_DETECT_UART_TX" in str(excinfo.value)
    assert "默认实例 UART1" in str(excinfo.value)


def test_uart_instance_conflict_gate_mspm0_swap_passes():
    """UART 换位（绑定×绑定）放行：IMU601→UART1 + DIGIT_UART→UART0 直过。"""
    _uart_conflict_check(UART_SWAP_BINDINGS)


def test_error_entry_maps_uart_instance_conflict_to_400():
    status, message = error_entry(
        UartInstanceConflictError(
            "绑定冲突：imu_uart.IMU601_TX（绑 PA8，推导实例 UART1）"
            "与未绑定的 digit_uart.DIGIT_UART_TX 默认实例 UART1 冲突"
        )
    )
    assert status == 400
    assert "默认实例 UART1" in message


# ---------------------------------------------------------------------------
# syscfg 改写器：peripheral 行联动 + 默认逐字节
# ---------------------------------------------------------------------------


def test_rewrite_syscfg_default_bindings_byte_identical():
    assert rewrite_syscfg(MSPM0_MASTER_SYSCFG, ()) == MSPM0_MASTER_SYSCFG
    assert (
        rewrite_syscfg(
            MSPM0_MASTER_SYSCFG,
            _resolve({"led.LED": "PA15"}),
        )
        == MSPM0_MASTER_SYSCFG
    )


def test_rewrite_syscfg_uart_swap_peripheral_and_pins():
    """UART 换位：引脚 $assign 与 peripheral $assign 联动改写；实例名/宏名/
    通道名不动（DIGIT_UART/IMU601 名字行原样）。"""
    out = rewrite_syscfg(MSPM0_MASTER_SYSCFG, _resolve(UART_SWAP_BINDINGS))
    assert 'IMU601.peripheral.$assign = "UART1";' in out
    assert 'IMU601.peripheral.txPin.$assign = "PA8";' in out
    assert 'IMU601.peripheral.rxPin.$assign = "PA9";' in out
    assert 'DIGIT_UART.peripheral.$assign = "UART0";' in out
    assert 'DIGIT_UART.peripheral.txPin.$assign = "PA28";' in out
    assert 'DIGIT_UART.peripheral.rxPin.$assign = "PA31";' in out
    assert 'IMU601.$name             = "IMU601";' in out
    assert 'DIGIT_UART.$name             = "DIGIT_UART";' in out


def test_rewrite_syscfg_pwm_same_instance_keeps_peripheral():
    """PWMAB_C0→PA23 同实例（TIMG0_C0 在候选内）→ 只换 ccp0Pin，peripheral
    行 TIMG0 逐字节不动（最小改动契约）。"""
    out = rewrite_syscfg(MSPM0_MASTER_SYSCFG, _resolve({"motor.PWMAB_C0": "PA23"}))
    assert 'PWMAB.peripheral.ccp0Pin.$assign = "PA23";' in out
    assert 'PWMAB.peripheral.$assign         = "TIMG0";' in out


def test_rewrite_syscfg_pwm_family_move_rewrites_peripheral():
    """PWMAB 同族换实例（04 起两通道同实例门禁在位，单脚绑 PA14 会被拦）：
    C0→PA14（TIMG12_C0）+ C1→PA25（TIMG12_C1）成对绑 → peripheral
    TIMG0→TIMG12 + 两通道引脚联动；通道名 ti_driverlib_pwm_PWMTimerCC0 不动。"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG,
        _resolve({"motor.PWMAB_C0": "PA14", "motor.PWMAB_C1": "PA25"}),
    )
    assert 'PWMAB.peripheral.$assign         = "TIMG12";' in out
    assert 'PWMAB.peripheral.ccp0Pin.$assign = "PA14";' in out
    assert 'PWMAB.peripheral.ccp1Pin.$assign = "PA25";' in out
    assert 'ti_driverlib_pwm_PWMTimerCC0' in out


def test_rewrite_syscfg_i2c_move_rewrites_peripheral():
    """OLED SCL/SDA 成对换到 I2C0 脚（PA0/PA1）→ peripheral I2C1→I2C0 +
    sda/scl 引脚联动。"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG,
        _resolve({"oled.OLED_SCL": "PA1", "oled.OLED_SDA": "PA0"}),
    )
    assert 'OLED.peripheral.$assign            = "I2C0";' in out
    assert 'OLED.peripheral.sclPin.$assign     = "PA1";' in out
    assert 'OLED.peripheral.sdaPin.$assign     = "PA0";' in out


def test_rewrite_syscfg_step_motor_port_group_pins_only():
    """step_motor 四脚换 GPIOA：只换四个 pin.$assign 行——母版无 port 字段、
    写侧不加（SysConfig 自动推导 STEP_MOTOR_PORT，前置验证 2026-08-15）。"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG,
        _resolve(
            {
                "step_motor.STEP_MOTOR_RST2": "PA15",
                "step_motor.STEP_MOTOR_SLP2": "PA16",
                "step_motor.STEP_MOTOR_DIR2": "PA17",
                "step_motor.STEP_MOTOR_DCY2": "PA18",
            }
        ),
    )
    assert 'STEP_MOTOR.associatedPins[0].pin.$assign  = "PA15";' in out
    assert 'STEP_MOTOR.associatedPins[1].pin.$assign  = "PA16";' in out
    assert 'STEP_MOTOR.associatedPins[2].pin.$assign  = "PA17";' in out
    assert 'STEP_MOTOR.associatedPins[3].pin.$assign  = "PA18";' in out
    assert "STEP_MOTOR.port" not in out
