"""stm32 默认布局不变量（工单 pin-full-unlock/05，数据工单）：默认引脚两两
互异 + 白名单共享。

工单 05 重排结论（证据 .scratch/pin-full-unlock/issues/05）：全库 stm32 42 个
角色声明 vs 排针 32 脚，物理上不可能全互异——UART1 三模块（digit/ball/uwb）
与 zigbee_uart/key 是既有设计共享；DIP×GRAY_D1-4（PB12-15）是唯一无法消解的
残留（详情见工单 Comments）。本测试把共享白名单钉死，防止重排成果回退。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"


def _stm32_roles() -> list[tuple[str, str]]:
    roles: list[tuple[str, str]] = []
    for module_dir in sorted(LIBRARY_MODULES.iterdir()):
        if not module_dir.is_dir():
            continue
        manifest = ModuleManifest.load(module_dir)
        entry = manifest.platforms.get("stm32")
        if entry is None:
            continue
        for pin in entry.pins:
            roles.append((manifest.slug, pin.id, pin.default))
    return roles


def _group_by_pin() -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for slug, role_id, default in _stm32_roles():
        grouped.setdefault(default, set()).add(f"{slug}.{role_id}")
    return grouped


# 共享白名单（同角色共享合法，按引脚精确钉死）。DIP×GRAY_D1-4 是工单 05
# 的残留项：全排针无额外 4 脚可挪（详见工单 Comments）。
WHITELIST = {
    "PA9": {
        "digit_uart.DIGIT_UART_TX",
        "ball_detect.BALL_DETECT_UART_TX",
        "uwb_uart.UWB_UART_TX",
    },
    "PA10": {
        "digit_uart.DIGIT_UART_RX",
        "ball_detect.BALL_DETECT_UART_RX",
        "uwb_uart.UWB_UART_RX",
    },
    "PB10": {
        "zigbee_uart.ZIGBEE_UART_TX",
        "zigbee_uart_key.ZIGBEE_UART_TX",
    },
    "PB11": {
        "zigbee_uart.ZIGBEE_UART_RX",
        "zigbee_uart_key.ZIGBEE_UART_RX",
    },
    "PB12": {"pid.GRAY_D1", "config.DIP0"},
    "PB13": {"pid.GRAY_D2", "config.DIP1"},
    "PB14": {"pid.GRAY_D3", "config.DIP2"},
    "PB15": {"pid.GRAY_D4", "config.DIP3"},
    # key stm32 默认 PB3 与 pid.GRAY_D6 重叠（蓝药丸无板载按键，PB3 = JTDO
    # 复位后可用；实际接线经引脚绑定消解——module-functionalize/04）
    "PB3": {"key.KEY_START", "pid.GRAY_D6"},
}


def test_default_layout_no_shared_pins_outside_whitelist():
    grouped = _group_by_pin()
    for pin, roles in sorted(grouped.items()):
        if len(roles) > 1:
            assert pin in WHITELIST, (
                f"{pin} 被多个角色共享但不在白名单：{sorted(roles)}"
            )
            assert roles == WHITELIST[pin], (
                f"{pin} 共享角色漂移：{sorted(roles)} ≠ {sorted(WHITELIST[pin])}"
            )


def test_default_layout_whitelist_pins_still_shared():
    grouped = _group_by_pin()
    for pin, expected in WHITELIST.items():
        assert grouped.get(pin) == expected, (
            f"{pin} 白名单共享已不成立：{grouped.get(pin)}"
        )


def test_default_layout_conflict_groups_resolved():
    """工单 05 五组冲突：四组已解（BUZZER/MOTOR_B_DIR、DEBUG/MOTOR_A_ENC、
    LED/GRAY_D6-8、ZIGBEE/软 I2C）；DIP×GRAY_D1-4 为白名单残留。"""
    grouped = _group_by_pin()
    assert grouped["PB0"] == {"motor.MOTOR_B_DIR"}
    assert grouped["PA2"] == {"debug_uart.DEBUG_UART_TX"}
    assert grouped["PA3"] == {"debug_uart.DEBUG_UART_RX"}
    assert grouped["PC13"] == {"config.LED_RED"}
    assert grouped["PC14"] == {"config.LED_YELLOW"}
    assert grouped["PC15"] == {"config.LED_GREEN"}
    assert grouped["PB10"] == {
        "zigbee_uart.ZIGBEE_UART_TX",
        "zigbee_uart_key.ZIGBEE_UART_TX",
    }
    assert grouped["PB11"] == {
        "zigbee_uart.ZIGBEE_UART_RX",
        "zigbee_uart_key.ZIGBEE_UART_RX",
    }
