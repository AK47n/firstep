"""mspm0 默认布局不变量（2026-09 批量模块入库审计补建）：默认引脚两两
互异 + 白名单共享——地猛星 2×20 排针默认脚全占（176 个角色挤 31 个默认脚、
27 组跨模块共享），按 CONTEXT 平台行「默认脚按同选概率最低者重叠、同选经
引脚绑定消解」的设计约定落盘。本测试把共享白名单逐组钉死（镜像 stm32 侧
test_default_layout.py），防止后续批次改默认脚时无意识漂移——新增共享组/
成员变更必须同步本白名单并附理由注释。

注：huidu/pid/xunji 三件默认脚完全一致属**相互斥组 gray-track 同一方案
三选一**（推荐互斥、永不双选），与其余交叉项（不同框件、同选概率低）一并
列入白名单——交叉项即「同选经绑定消解」的真实来源。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"


def _mspm0_roles() -> list[tuple[str, str, str]]:
    roles: list[tuple[str, str, str]] = []
    for module_dir in sorted(LIBRARY_MODULES.iterdir()):
        if not module_dir.is_dir():
            continue
        manifest = ModuleManifest.load(module_dir)
        entry = manifest.platforms.get("mspm0")
        if entry is None:
            continue
        for pin in entry.pins:
            roles.append((manifest.slug, pin.id, pin.default))
    return roles


def _group_by_pin() -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for slug, role_id, default in _mspm0_roles():
        grouped.setdefault(default, set()).add(f"{slug}.{role_id}")
    return grouped


# 共享白名单（同默认脚合法，按引脚精确钉死；理由 = 同选概率最低/不同框/
# 互斥组/同总线族）。变更必须同步此处并附注释。
WHITELIST = {
    "PA0": {  # I2C_0 SDA × 红外发射：姿态采集 × 红外链路不同框
        "ir_remote_tx.IR_TX_OUT",
        "ml_mpu6050.I2C_0_SDA",
    },
    "PA1": {  # I2C_0 SCL × 粉尘 LED × 继电器：姿态/粉尘 × 执行机构不同框
        "gp2y1014au.GP2Y1014_LED",
        "ml_mpu6050.I2C_0_SCL",
        "relay.RELAY_OUT",
    },
    "PA7": {  # 电机 BIN2 方向 × 舵机 PWM × 单总线 × 射频 SCK：运动/感知不同框
        "ds18b20.DS18B20_DATA",
        "motor.BIN2",
        "rc522.RC522_CS",
        "servo.SERVO_PWM_C0",
    },
    "PA8": {  # DIGIT_UART TX 族（digit/coord/open_mv4）× 状态/红外/触摸/软I2C
        "coord_detect.COORD_DETECT_UART_TX",
        "digit_uart.DIGIT_UART_TX",
        "hc05.HC05_STATE",
        "ir_beam.IR_BEAM_OUT",
        "mlx90614.MLX90614_SDA",
        "open_mv4.OPENMV4_UART_TX",
        "tp_xpt2046.TP_XPT2046_CS",
    },
    "PA9": {  # DIGIT_UART RX 族 × 摇杆 SW × 无线 MISO/软I2C
        "coord_detect.COORD_DETECT_UART_RX",
        "digit_uart.DIGIT_UART_RX",
        "joystick.JOYSTICK_SW",
        "mlx90614.MLX90614_SCL",
        "nrf24l01.NRF24L01_MISO",
        "open_mv4.OPENMV4_UART_RX",
        "tp_xpt2046.TP_XPT2046_DIN",
    },
    "PA12": {  # 电机 PWM C0 × 软 I2C × 指纹 TOUCH：运动/采集/身份不同框
        "bh1750.BH1750_SCL",
        "fingerprint.FINGERPRINT_TOUCH",
        "motor.PWMAB_C0",
    },
    "PA13": {  # 电机 PWM C1 × 软 I2C/显示 DC/触摸 CLK
        "bh1750.BH1750_SDA",
        "motor.PWMAB_C1",
        "oled.OLED_SPI_DC",
        "tp_xpt2046.TP_XPT2046_CLK",
    },
    "PA14": {  # 步进 PWM × 软 I2C/SPI SCK/ADC CH7/灯带：步进执行 × 采集不同框
        "ags10.AGS10_SDA",
        "l298n.L298N_PWM_C0",
        "rc522.RC522_SCK",
        "soil.SOIL_AO_CH7",
        "step_motor.DCC_100_PWM2_C0",
        "ws2812.WS2812_IN",
    },
    "PA16": {  # 编码器 AA × 软 I2C/SPI MOSI
        "ads1115.ADS1115_SCL",
        "lcd.LCD_SCL",
        "motor.AA",
        "rc522.RC522_MOSI",
        "sht20.SHT20_SCL",
    },
    "PA17": {  # 编码器 AB × 软 I2C/SPI MISO
        "ads1115.ADS1115_SDA",
        "lcd.LCD_SDA",
        "motor.AB",
        "rc522.RC522_MISO",
        "sht20.SHT20_SDA",
    },
    "PA18": {  # 电机 AIN2 × 显示 CLK/SPI RST/软 I2C
        "max7219.MAX7219_CLK",
        "motor.AIN2",
        "rc522.RC522_RST",
        "sgp30.SGP30_SCL",
    },
    "PA22": {  # HUIDU L1 × GRAY_D1 × xunji P3（互斥组 gray-track）+ OLED RES/红外/ADC/无线不同框
        "debug_uart.DEBUG_UART_RX",
        "flame.FLAME_AO_CH6",
        "huidu.L1",
        "lcd.LCD_DC",
        "nrf24l01.NRF24L01_IRQ",
        "oled.OLED_SPI_RES",
        "pid.GRAY_D1",
        "ttp224.TTP224_OUT1",
        "xunji.P3",
    },
    "PA23": {  # HUIDU L2 × GRAY_D2 × xunji P2 + UART TX 族/软 I2C/无线 CE
        "bmp180.BMP180_SCL",
        "debug_uart.DEBUG_UART_TX",
        "hc05.HC05_TX",
        "huidu.L2",
        "nrf24l01.NRF24L01_CE",
        "pid.GRAY_D2",
        "tcs34725.TCS34725_SCL",
        "uwb_uart.UWB_UART_TX",
        "xunji.P2",
    },
    "PA24": {  # ADC12_0 MEM0 共读同槽族（adc 薄封装 × ADC 模拟量）× 灰度 × UART RX
        "adc.ADC_CH0",
        "bmp180.BMP180_SDA",
        "gp2y1014au.GP2Y1014_AO_CH0",
        "hc05.HC05_RX",
        "huidu.L3",
        "mq2.MQ2_AO_CH0",
        "mq3.MQ3_AO_CH0",
        "mq4.MQ4_AO_CH0",
        "mq6.MQ6_AO_CH0",
        "mq7.MQ7_AO_CH0",
        "mq8.MQ8_AO_CH0",
        "mq9.MQ9_AO_CH0",
        "ms1100.MS1100_AO_CH0",
        "nrf24l01.NRF24L01_CSN",
        "photoresistance.PHOTORESISTANCE_AO_CH0",
        "pid.GRAY_D3",
        "rain.RAIN_AO_CH0",
        "s12sd.S12SD_AO_CH0",
        "tcs34725.TCS34725_SDA",
        "us016.US016_OUT_CH0",
        "uwb_uart.UWB_UART_RX",
        "xunji.P1",
    },
    "PA25": {  # HUIDU L4 × GRAY_D4 × xunji P6 + ZIGBEE RX 族/摇杆 Y/无线 MOSI
        "as32.AS32_UART_RX",
        "huidu.L4",
        "joystick.JOYSTICK_Y_CH2",
        "nrf24l01.NRF24L01_MOSI",
        "pid.GRAY_D4",
        "ttp224.TTP224_OUT2",
        "xunji.P6",
        "zigbee_link.ZIGBEE_UART_RX",
        "zigbee_uart.ZIGBEE_UART_RX",
        "zigbee_uart_key.ZIGBEE_UART_RX",
    },
    "PA26": {  # HUIDU R1 × GRAY_D5 × xunji P4 + ZIGBEE TX 族/摇杆 X/红外接收/无线 CLK
        "as32.AS32_UART_TX",
        "huidu.R1",
        "ir_remote.IR_REMOTE_OUT",
        "joystick.JOYSTICK_X_CH1",
        "nrf24l01.NRF24L01_CLK",
        "pid.GRAY_D5",
        "ttp224.TTP224_OUT3",
        "xunji.P4",
        "zigbee_link.ZIGBEE_UART_TX",
        "zigbee_uart.ZIGBEE_UART_TX",
        "zigbee_uart_key.ZIGBEE_UART_TX",
    },
    "PA27": {  # HUIDU R2 × GRAY_D6 × xunji P5 + ADC CH3/显示 RES/触摸/执行
        "huidu.R2",
        "ir_distance.IR_DIST_OUT_CH3",
        "l298n.L298N_EN",
        "lcd.LCD_RES",
        "pid.GRAY_D6",
        "ttp224.TTP224_OUT4",
        "xunji.P5",
    },
    "PA28": {  # 指纹 TX/IMU601 TX（UART 族）× 称重 SCK/软 I2C/触摸 DOUT
        "fingerprint.FINGERPRINT_TX",
        "hx711.HX711_SCK",
        "imu_uart.IMU601_TX",
        "jy61p.JY61P_SCL",
        "ms5611.MS5611_SCL",
        "oled.OLED_SPI_SCL",
        "sht30.SHT30_SCL",
        "tp_xpt2046.TP_XPT2046_DOUT",
    },
    "PA31": {  # 指纹 RX/IMU601 RX（UART 族）× 称重 DT/软 I2C/微波/触摸 PEN
        "fingerprint.FINGERPRINT_RX",
        "hx711.HX711_DT",
        "imu_uart.IMU601_RX",
        "jy61p.JY61P_SDA",
        "microwave_radar.MICROWAVE_OUT",
        "ms5611.MS5611_SDA",
        "oled.OLED_SPI_SDA",
        "sht30.SHT30_SDA",
    },
    "PB6": {  # 灰度 R3/GRAY_D7/xunji P7 + AHT10/PCA9685 软 I2C + 步进 SLP2
        "aht10.AHT10_SCL",
        "huidu.R3",
        "pca9685.PCA9685_SCL",
        "pid.GRAY_D7",
        "step_motor.STEP_MOTOR_SLP2",
        "xunji.P7",
    },
    "PB7": {  # 灰度 R4/GRAY_D8/xunji P8 + AHT10/PCA9685 软 I2C + DHT11 + 步进 DIR2
        "aht10.AHT10_SDA",
        "dht11.DHT11_DATA",
        "huidu.R4",
        "pca9685.PCA9685_SDA",
        "pid.GRAY_D8",
        "step_motor.STEP_MOTOR_DIR2",
        "xunji.P8",
    },
    "PB8": {  # 软 I2C × 人体红外 × 超声 ECHO × 步进 DCY2
        "at24c02.AT24C02_SDA",
        "human_ir.HUMAN_IR_OUT",
        "sr04.SR04_ECHO",
        "step_motor.STEP_MOTOR_DCY2",
    },
    "PB9": {  # 显示 DIN × 电机 AIN1 × 软 I2C
        "max7219.MAX7219_DIN",
        "motor.AIN1",
        "sgp30.SGP30_SDA",
    },
    "PB18": {  # 显示 CS × 电机 BIN1 × 软 I2C
        "ags10.AGS10_SCL",
        "max7219.MAX7219_CS",
        "motor.BIN1",
        "oled.OLED_SPI_CS",
    },
    "PB19": {  # 软 UART TX（jq8900）× 显示 CS × 编码器 BA
        "jq8900.JQ8900_TX",
        "lcd.LCD_CS",
        "motor.BA",
    },
    "PB20": {  # 软 UART TX（syn6288）× 显示 BLK × 编码器 BB × MQ135 MEM4
        "lcd.LCD_BLK",
        "motor.BB",
        "mq135.MQ135_AO_CH4",
        "syn6288.SYN6288_TX",
    },
    "PB24": {  # 步进 RST2 × 软 I2C × L298N PWM C1 × MQ5 MEM5 × 超声 TRIG × 触摸 PEN
        "at24c02.AT24C02_SCL",
        "hc05.HC05_KEY",
        "l298n.L298N_PWM_C1",
        "mq5.MQ5_AO_CH5",
        "sr04.SR04_TRIG",
        "step_motor.STEP_MOTOR_RST2",
        "tp_xpt2046.TP_XPT2046_PEN",
    },
}


def test_mspm0_default_layout_whitelist():
    """共享脚全部在白名单内、且成员集合精确一致（防漂移）。"""
    grouped = _group_by_pin()
    for pin, roles in grouped.items():
        if len(roles) < 2:
            continue
        assert pin in WHITELIST, (
            f"{pin} 被多个角色共享但不在白名单：{sorted(roles)}"
        )
        assert roles == WHITELIST[pin], (
            f"{pin} 共享角色漂移：{sorted(roles)} ≠ {sorted(WHITELIST[pin])}"
        )


def test_mspm0_default_layout_whitelist_still_holds():
    """白名单共享已不成立 = 漂移或误删（反向钉死）。"""
    grouped = _group_by_pin()
    for pin, expected in WHITELIST.items():
        assert grouped.get(pin) == expected, (
            f"{pin} 白名单共享已不成立：{sorted(grouped.get(pin, set()))}"
        )
