"""stm32 默认布局不变量（工单 pin-full-unlock/05，数据工单）：默认引脚两两
互异 + 白名单共享。

工单 05 重排结论（证据 .scratch/pin-full-unlock/issues/05）：全库 stm32 42 个
角色声明 vs 排针 32 脚，物理上不可能全互异——UART1 三模块（digit/coord/uwb）
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
        "coord_detect.COORD_DETECT_UART_TX",
        "uwb_uart.UWB_UART_TX",
    },
    "PA10": {
        "digit_uart.DIGIT_UART_RX",
        "coord_detect.COORD_DETECT_UART_RX",
        "uwb_uart.UWB_UART_RX",
    },
    "PB10": {
        "zigbee_uart.ZIGBEE_UART_TX",
        "zigbee_uart_key.ZIGBEE_UART_TX",
        "zigbee_link.ZIGBEE_UART_TX",
    },
    "PB11": {
        "zigbee_uart.ZIGBEE_UART_RX",
        "zigbee_uart_key.ZIGBEE_UART_RX",
        "zigbee_link.ZIGBEE_UART_RX",
    },
    # PB12-15 三共享（DIP×GRAY×TTP224——wiki-stm32-batch1/05，见下方批次 1 注释块）
    # key stm32 默认 PB3 与 pid.GRAY_D6 重叠（蓝药丸无板载按键，PB3 = JTDO
    # 复位后可用；实际接线经引脚绑定消解——module-functionalize/04）
    "PB3": {"key.KEY_START", "pid.GRAY_D6"},
    # adc 默认 PA0/PA1 与 motor PWM 重叠（b1-adc-servo/01）：蓝药丸 ADC 通道
    # 脚（PA0-7/PB0-1）全部被既有模块占用，无空闲可挪——实际接线经引脚绑定
    # 消解；adc 与 motor 同用时必须改绑
    "PA0": {"motor.MOTOR_A_PWM", "adc.ADC_CH0"},
    "PA1": {"motor.MOTOR_B_PWM", "adc.ADC_CH1"},
    # servo 默认 PB6 与 pid.GRAY_D7 重叠（b1-adc-servo/02）：蓝药丸可 PWM 脚
    # 全被占用，无空闲可挪——实际接线经引脚绑定消解
    "PB6": {"pid.GRAY_D7", "servo.SERVO_PWM_C0"},
    # PA8 三共享（ir_beam×pid.GRAY_D5 为 ir-beam-module/01 残留；ws2812 为
    # wiki-stm32-batch1/06 批次 1 新增——幻彩灯带与「红外对射/巡线」不同框、
    # 同选概率最低（刻意不叠灯族 LED PC13-15），同选经引脚绑定消解）
    "PA8": {"pid.GRAY_D5", "ir_beam.IR_BEAM_OUT", "ws2812.WS2812_DIN"},
    # relay 默认 PB4 与 motor 编码器方向输入重叠（继电器≠编码器闭环；
    # 刻意不叠声光/执行件 LED/BUZZER/电机 PWM/方向）
    "PB4": {"motor.MOTOR_A_ENC_DIR", "relay.RELAY_OUT"},
    # human_ir 默认 PB7 与 pid 灰度 GRAY_D8 重叠（人体红外≠巡线灰度；
    # 刻意避让声光/按键/门禁组合 BUZZER/KEY/SERVO）
    "PB7": {"pid.GRAY_D8", "human_ir.HUMAN_IR_OUT"},
    # microwave_radar 默认 PA4 与 motor 编码器 B 相 EXTI 重叠（微波雷达≠
    # 编码器闭环；刻意避让声光/门禁/传感站组合件；本件轮询不注册 EXTI）
    "PA4": {"motor.MOTOR_B_ENC", "microwave_radar.MICROWAVE_OUT"},
    # flame 默认 PA5 与 motor 编码器方向输入 MOTOR_B_ENC_DIR 重叠（火焰≠
    # 编码器闭环；stm32 ADC 可达脚 PA0-7/PB0-1 全被既有角色占用——取最
    # 「不同框」的 PA5（避让 PWM 主脚 PA0/1、debug PA2/3、编码器 EXTI PA4/PB5））
    "PA5": {"motor.MOTOR_B_ENC_DIR", "flame.FLAME_AO"},
    # ttp224 默认 PB12-15 与 config DIP0-3 + pid GRAY_D1-4 重叠（触摸按键≠
    # 拨码配置/巡线灰度；四脚同口约束——换口需整组迁移，同选经引脚绑定消解）
    "PB12": {"pid.GRAY_D1", "config.DIP0", "ttp224.TTP224_OUT1"},
    "PB13": {"pid.GRAY_D2", "config.DIP1", "ttp224.TTP224_OUT2"},
    "PB14": {"pid.GRAY_D3", "config.DIP2", "ttp224.TTP224_OUT3"},
    "PB15": {"pid.GRAY_D4", "config.DIP3", "ttp224.TTP224_OUT4"},
    # PA6/PA7 软 I2C 总线共享组（wiki-stm32-batch2/01 起，六件共总线：
    # aht10/bh1750/sht20/sht30/at24c02/ags10 默认 SCL=PA6/SDA=PA7——器件
    # 地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异、多挂协议允许 = 合法共享
    # （_shared_groups 判 kind=share「I2C 总线共享」），随工单逐个入组；
    # 与 motor MOTOR_A_DIR/DIR2（TB6612 A 相方向）重叠：环境传感/存储记录
    # 与「带电机方向的小车运动控制」不同框、同选概率最低（刻意不叠显示/
    # 声光/输入/串口/无线/USB/SWD 组），同选经引脚绑定消解）
    "PA6": {
        "motor.MOTOR_A_DIR",
        "aht10.AHT10_SCL",
        "bh1750.BH1750_SCL",
        "sht20.SHT20_SCL",
        "sht30.SHT30_SCL",
    },
    "PA7": {
        "motor.MOTOR_A_DIR2",
        "aht10.AHT10_SDA",
        "bh1750.BH1750_SDA",
        "sht20.SHT20_SDA",
        "sht30.SHT30_SDA",
    },
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
        "zigbee_link.ZIGBEE_UART_TX",
    }
    assert grouped["PB11"] == {
        "zigbee_uart.ZIGBEE_UART_RX",
        "zigbee_uart_key.ZIGBEE_UART_RX",
        "zigbee_link.ZIGBEE_UART_RX",
    }
