"""mspm0 PWM 跨外设族（工单 pin-full-unlock/04，ADR 0012 Tier B）：pwm 全
类型级（跨族放开、通道仍按角色尾过滤）+ PWMAB 两通道同实例门禁 + syscfg
peripheral 跨族改写（TIMG0→TIMA0）。

数据裁决（2026-08-15）：TIMA0 排针 C0+C1 对 = PA0/PA1、PA8/PA9、PB8/PB9；
TIMA1 = PA15/PA16、PA17/PA18、PB2/PB3、PA28/PA31 → 跨族物理可达。真机探针
实证 motor.c 用 SDK 通用 DL_Timer_* API（DL_TimerA_*/DL_TimerG_* 只是重定向
宏），TIMA0 生成工程 clean all 0 错 → motor 双分支 / pin_family.h 均不需要
（偏差留痕工单 Comments）。红证 = 两通道异实例 400 / 通道不匹配 400；绿证 =
跨族字段断言 + 默认逐字节。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.boards import BOARDS_DIR, load_boards
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


def _resolve(bindings: dict[str, str]):
    return resolve_bindings(ALL_MANIFESTS, "mspm0", BOARDS["mspm0"], bindings)


# ---------------------------------------------------------------------------
# resolve：pwm 全类型级 + 两通道同实例门禁
# ---------------------------------------------------------------------------


def test_resolve_pwm_cross_family_pair_tima0():
    """跨族类型级：PWMAB C0→PA8（TIMA0_C0）+ C1→PA9（TIMA0_C1）两通道同
    实例 TIMA0 → 放行，实例随绑定引脚推导。"""
    resolved = _resolve({"motor.PWMAB_C0": "PA8", "motor.PWMAB_C1": "PA9"})
    assert {b.role_key: b.instances for b in resolved} == {
        "motor.PWMAB_C0": ("TIMA0_C0",),
        "motor.PWMAB_C1": ("TIMA0_C1",),
    }


def test_resolve_pwm_two_channels_different_instances_400():
    """两通道同实例门禁：C0→PA8（TIMA0）× C1→PA13（TIMG0_C1）基名交集空 →
    400 中文"两通道必须同实例，请成对绑定"。"""
    with pytest.raises(PinBindingError, match="两通道必须同实例") as excinfo:
        _resolve({"motor.PWMAB_C0": "PA8", "motor.PWMAB_C1": "PA13"})
    assert "PWMAB_C0" in str(excinfo.value)
    assert "PWMAB_C1" in str(excinfo.value)


def test_resolve_pwm_single_channel_move_400():
    """只绑 C0→PA8（C1 留默认 TIMG0_C1）→ 两通道异实例 400（成对绑定语义）。"""
    with pytest.raises(PinBindingError, match="两通道必须同实例"):
        _resolve({"motor.PWMAB_C0": "PA8"})


def test_resolve_pwm_channel_mismatch_400():
    """通道下限：PWMAB_C1 → PA8（只有 TIMA0_C0 / TIMA1_C0N，无 C1）→ 400。"""
    with pytest.raises(PinBindingError, match="pwm 通道 C1"):
        _resolve({"motor.PWMAB_C1": "PA8"})


def test_resolve_pwm_same_family_regression_still_passes():
    """同族路径回归（03 语义）：PWMAB C0/C1 默认同 TIMG0 时零绑定直过；
    绑定 = 默认值 no-op 直过。"""
    assert _resolve({}) == ()
    resolved = _resolve({"motor.PWMAB_C0": "PA12", "motor.PWMAB_C1": "PA13"})
    assert len(resolved) == 2


# ---------------------------------------------------------------------------
# 写侧：peripheral 跨族改写（TIMG0→TIMA0）+ 默认逐字节
# ---------------------------------------------------------------------------


def test_rewrite_syscfg_cross_family_peripheral_and_pins():
    """跨族绑定：PWMAB peripheral TIMG0→TIMA0 + ccp0/ccp1 换 PA8/PA9；实例名
    / 通道名不动。"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG,
        _resolve({"motor.PWMAB_C0": "PA8", "motor.PWMAB_C1": "PA9"}),
    )
    assert 'PWMAB.peripheral.$assign         = "TIMA0";' in out
    assert 'PWMAB.peripheral.ccp0Pin.$assign = "PA8";' in out
    assert 'PWMAB.peripheral.ccp1Pin.$assign = "PA9";' in out
    assert 'PWMAB.$name                      = "PWMAB";' in out
    assert 'ti_driverlib_pwm_PWMTimerCC0' in out


def test_rewrite_syscfg_default_bindings_byte_identical():
    assert rewrite_syscfg(MSPM0_MASTER_SYSCFG, ()) == MSPM0_MASTER_SYSCFG
    assert (
        rewrite_syscfg(
            MSPM0_MASTER_SYSCFG,
            _resolve({"motor.PWMAB_C0": "PA12", "motor.PWMAB_C1": "PA13"}),
        )
        == MSPM0_MASTER_SYSCFG
    )
