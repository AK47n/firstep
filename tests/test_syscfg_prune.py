"""mspm0 syscfg 动态裁剪（工单 syscfg-prune/01）：按选中模块集裁掉未选实例。

契约：全选理论模块 == 母版逐字节；空选裁掉全部外设实例（Board/SYSCTL 保留）；
选 motor 只留 motor 消费的实例（PWMAB/MOTOR_PID/DC_MOTOR + Board/SYSCTL）；
共享实例任一消费模块选中即保留（选 key 留 DC_MOTOR/KEY；选 pid 留 HUIDU）。
"""

from __future__ import annotations

import re
from pathlib import Path

from contest_generator.syscfg_prune import INSTANCE_CONSUMERS, prune_syscfg

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MASTER_SYSCFG = (
    LIBRARY_ROOT / "masters" / "mspm0" / "mspm0.syscfg"
).read_text(encoding="utf-8", newline="")


def test_prune_all_selected_is_byte_identical():
    selected = sorted({s for consumers in INSTANCE_CONSUMERS.values() for s in consumers})
    assert prune_syscfg(MASTER_SYSCFG, selected) == MASTER_SYSCFG


def _assert_instance_present(text: str, instance: str) -> None:
    assert re.search(rf"^\s*const\s+{instance}\s*=", text, re.M), instance
    assert re.search(rf"^\s*{instance}\.", text, re.M), instance


def _assert_instance_absent(text: str, instance: str) -> None:
    assert not re.search(rf"^\s*const\s+{instance}\s*=", text, re.M), instance
    assert not re.search(rf"^\s*{instance}\.", text, re.M), instance


def test_prune_empty_removes_all_peripheral_instances():
    out = prune_syscfg(MASTER_SYSCFG, [])
    for instance in INSTANCE_CONSUMERS:
        _assert_instance_absent(out, instance)
    assert "const Board = scripting.addModule" in out
    assert "SYSCTL" in out


def test_prune_motor_keeps_only_motor_instances():
    out = prune_syscfg(MASTER_SYSCFG, ["motor"])
    for keep in ("PWMAB", "DC_MOTOR"):
        _assert_instance_present(out, keep)
    for drop in ("DCC_100_PWM2", "MOTOR_PID", "NTB", "HUIDU", "KEY", "LED_BEEP",
                 "STEP_MOTOR", "IMU601", "DIGIT_UART", "UWB_UART", "OLED", "I2C_0"):
        _assert_instance_absent(out, drop)
    # 模块变量：GPIO 被 DC_MOTOR 使用，PWM 被 PWMAB 使用；MOTOR_PID 随旧
    # PID 逻辑剥离不再被 motor 消费，TIMER 一并裁掉
    assert "const TIMER" not in out and "const GPIO" in out and "const PWM" in out
    # 未使用的 UART / I2C 模块变量连 addModule 一起裁掉
    assert "const UART" not in out
    assert "const I2C" not in out


def test_prune_shared_instance_kept_by_any_consumer():
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["motor"]), "DC_MOTOR")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["key"]), "DC_MOTOR")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["key"]), "KEY")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["pid"]), "HUIDU")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["pid"]), "MOTOR_PID")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["xunji"]), "HUIDU")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ball_detect"]), "DIGIT_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["zigbee_uart"]), "ZIGBEE_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["zigbee_uart_key"]), "ZIGBEE_UART")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["digit_uart"]), "ZIGBEE_UART")


def test_every_master_instance_is_registered_in_consumer_map():
    """母版新增 UART/外设实例必须登记消费映射——漏登记靠 prune 防御保留会
    让「未选模块的实例不落盘」失效（本批 UWB/ZIGBEE 曾缺）。"""
    declared = {
        m.group(1)
        for line in MASTER_SYSCFG.splitlines()
        if (m := re.match(r"^\s*const\s+([A-Za-z_]\w*)\s*=\s*[A-Za-z_\w]+\.addInstance\(\);?\s*$", line))
    }
    assert declared
    assert declared <= set(INSTANCE_CONSUMERS), declared - set(INSTANCE_CONSUMERS)
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["uwb_uart"]), "UWB_UART")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["digit_uart"]), "UWB_UART")
