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
        # wiki-stm32-batch7/05：key_matrix COL1——键盘与视觉/数传链路不同框、
        # 同选概率最低（列输入上拉——UART TX 点复用物理脚不同框），
        # 同选经引脚绑定消解
        "key_matrix.KEY_MATRIX_COL1",
        # wiki-stm32-batch8/02：hc05 TX——蓝牙与 UWB 室内定位链路**互替件
        # 同脚先例**（mspm0 定稿同款推理：默认×默认共享合法、门禁只查用户
        # 绑定），同选经绑定换实例成对消解
        "hc05.HC05_TX",
        # wiki-stm32-batch8/06：ir_remote_tx OUT——红外发射与视觉/数传链路
        # 不同框、同选概率最低（mspm0 默认 PA0 同型推理）；与 ir_remote 接收
        # 默认 PA10 刻意错开（发/收常配对、双选默认不撞），同选经绑定消解
        "ir_remote_tx.IR_TX_OUT",
        # wiki-stm32-batch9/03：fingerprint TX——指纹与 K230 视觉**身份识别
        # 互替件同脚先例**（mspm0 指纹独立实例、K230 视觉 = DIGIT_UART——
        # stm32 同款推理挂 UART_1 宿主），同选经绑定换实例成对消解
        "fingerprint.FINGERPRINT_TX",
        # wiki-stm32-batch9/05：neo_6m TX——GPS 室外定位 × UWB 室内定位链路
        # **互替件同脚先例**（定位互替、同选概率最低；同选经绑定消解）
        "neo_6m.NEO_6M_TX",
    },
    "PA10": {
        "digit_uart.DIGIT_UART_RX",
        "coord_detect.COORD_DETECT_UART_RX",
        "uwb_uart.UWB_UART_RX",
        # wiki-stm32-batch7/03：joystick SW——摇杆与视觉/数传链路不同框、
        # 同选概率最低（mspm0 SW=PA9 同款推理），同选经绑定消解
        "joystick.JOYSTICK_SW",
        # wiki-stm32-batch7/05：key_matrix COL2——与 joystick SW 并列登记
        # （键盘/摇杆同为输入件、同选概率最低，同选经绑定消解）
        "key_matrix.KEY_MATRIX_COL2",
        # wiki-stm32-batch8/02：hc05 RX——与 TX 同策略（UWB 互替同脚）
        "hc05.HC05_RX",
        # wiki-stm32-batch8/05：ir_remote OUT——红外遥控与视觉/UWB 链路不同框、
        # 同选概率最低（mspm0 默认 PA26（UART 族）同型推理；轮询忙等不注册
        # EXTI——与编码器线共享正交不冲突），同选经绑定消解
        "ir_remote.IR_REMOTE_OUT",
        # wiki-stm32-batch9/03：fingerprint RX——与 TX 同策略（身份识别互替同脚）
        "fingerprint.FINGERPRINT_RX",
        # wiki-stm32-batch9/05：neo_6m RX——与 TX 同策略（定位互替同脚）
        "neo_6m.NEO_6M_RX",
    },
    "PB10": {
        "zigbee_uart.ZIGBEE_UART_TX",
        "zigbee_uart_key.ZIGBEE_UART_TX",
        "zigbee_link.ZIGBEE_UART_TX",
        # wiki-stm32-batch7/05：key_matrix COL3——键盘与无线数传链路不同框、
        # 同选概率最低，同选经引脚绑定消解
        "key_matrix.KEY_MATRIX_COL3",
        # wiki-stm32-batch8/01：as32 TX——LoRa 与 Zigbee 无线数传**互替件
        # 同脚先例**（二选一接入无需另消解；罕见同选经绑定换实例/换脚）
        "as32.AS32_UART_TX",
        # wiki-stm32-batch8/03：nrf24l01 CLK——2.4G 与 Zigbee/LoRa 无线数传
        # 互替件同脚（与键盘 COL3 并列，无线链路与手动输入不同框）
        "nrf24l01.NRF24L01_CLK",
    },
    "PB11": {
        "zigbee_uart.ZIGBEE_UART_RX",
        "zigbee_uart_key.ZIGBEE_UART_RX",
        "zigbee_link.ZIGBEE_UART_RX",
        # wiki-stm32-batch7/05：key_matrix COL4——键盘与无线数传链路不同框、
        # 同选概率最低，同选经引脚绑定消解
        "key_matrix.KEY_MATRIX_COL4",
        # wiki-stm32-batch8/01：as32 RX——与 TX 同策略（无线数传互替同脚）
        "as32.AS32_UART_RX",
        # wiki-stm32-batch8/03：nrf24l01 MOSI——与 CLK 同策略（无线互替同脚）
        "nrf24l01.NRF24L01_MOSI",
    },
    # PB12-15 三共享（DIP×GRAY×TTP224——wiki-stm32-batch1/05，见下方批次 1 注释块）
    # key stm32 默认 PB3 与 pid.GRAY_D6 重叠（蓝药丸无板载按键，PB3 = JTDO
    # 复位后可用；实际接线经引脚绑定消解——module-functionalize/04）
    # dht11 默认 PB3 三叠（wiki-stm32-batch4/03：环境件与独立按键/巡线不同框、
    # 同选概率最低；页面默认 PB0 不采用 = MOTOR_B_DIR；单总线件不叠软 I2C 总线）
    "PB3": {"key.KEY_START", "pid.GRAY_D6", "dht11.DHT11_DATA"},
    # adc 默认 PA0/PA1 与 motor PWM 重叠（b1-adc-servo/01）：蓝药丸 ADC 通道
    # 脚（PA0-7/PB0-1）全部被既有模块占用，无空闲可挪——实际接线经引脚绑定
    # 消解；adc 与 motor 同用时必须改绑
    # **wiki-stm32-batch7/03**：joystick X/Y 并入 PA1/PA0——与 adc 模块
    # ADC_CH1/CH0 **ADC 共享组**（mspm0 MEM1/2 与 adc 模块共享实例同构；
    # 摇杆手动输入与视觉/数传不同框，同选概率最低）
    "PA0": {"motor.MOTOR_A_PWM", "adc.ADC_CH0", "joystick.JOYSTICK_Y"},
    "PA1": {"motor.MOTOR_B_PWM", "adc.ADC_CH1", "joystick.JOYSTICK_X"},
    # servo 默认 PB6 与 pid.GRAY_D7 重叠（b1-adc-servo/02）：蓝药丸可 PWM 脚
    # 全被占用，无空闲可挪——实际接线经引脚绑定消解
    # **wiki-stm32-batch8/04**：rc522 SCK 并入 PB6——读卡与舵机/巡线不同框
    "PB6": {"pid.GRAY_D7", "servo.SERVO_PWM_C0", "rc522.RC522_SCK"},
    # PA8 三共享（ir_beam×pid.GRAY_D5 为 ir-beam-module/01 残留；ws2812 为
    # wiki-stm32-batch1/06 批次 1 新增——幻彩灯带与「红外对射/巡线」不同框、
    # 同选概率最低（刻意不叠灯族 LED PC13-15），同选经引脚绑定消解）
    # **wiki-stm32-batch8/02**：hc05 STATE 并入 PA8——蓝牙连接状态与红外
    # 对射/灯带/巡线不同框、同选概率最低（mspm0 STATE 同脚 PA8 同款推理）
    "PA8": {
        "pid.GRAY_D5",
        "ir_beam.IR_BEAM_OUT",
        "ws2812.WS2812_DIN",
        "hc05.HC05_STATE",
    },
    # relay 默认 PB4 与 motor 编码器方向输入重叠（继电器≠编码器闭环；
    # 刻意不叠声光/执行件 LED/BUZZER/电机 PWM/方向）
    # **wiki-stm32-batch8/02**：hc05 KEY 并入 PB4——AT 切换不常用，与继电器/
    # 编码器方向低频重叠（蓝牙+继电器控制/编码器闭环不同框）
    "PB4": {
        "motor.MOTOR_A_ENC_DIR",
        "relay.RELAY_OUT",
        "hc05.HC05_KEY",
        # wiki-stm32-batch8/03：nrf24l01 MISO——2.4G 无线与继电器/编码器方向
        # 不同框、同选概率最低（软 SPI 输入脚同为低频组合）
        "nrf24l01.NRF24L01_MISO",
        # wiki-stm32-batch8/04：rc522 MOSI——读卡与继电器/编码器方向不同框
        "rc522.RC522_MOSI",
    },
    # human_ir 默认 PB7 与 pid 灰度 GRAY_D8 重叠（人体红外≠巡线灰度；
    # 刻意避让声光/按键/门禁组合 BUZZER/KEY/SERVO）
    "PB7": {"pid.GRAY_D8", "human_ir.HUMAN_IR_OUT"},
    # microwave_radar 默认 PA4 与 motor 编码器 B 相 EXTI 重叠（微波雷达≠
    # 编码器闭环；刻意避让声光/门禁/传感站组合件；本件轮询不注册 EXTI）
    # **wiki-stm32-batch7/04**：ec11 A 相并入 PA4——EC11 人机旋钮与微波雷达/
    # 编码器闭环不同框（本件轮询不注册 EXTI——与编码器线共享正交，EXTI 门禁
    # 默认组合不拦），同选经引脚绑定消解
    "PA4": {
        "motor.MOTOR_B_ENC",
        "microwave_radar.MICROWAVE_OUT",
        "ec11.EC11_A",
    },
    # flame 默认 PA5 与 motor 编码器方向输入 MOTOR_B_ENC_DIR 重叠（火焰≠
    # 编码器闭环；stm32 ADC 可达脚 PA0-7/PB0-1 全被既有角色占用——取最
    # 「不同框」的 PA5（避让 PWM 主脚 PA0/1、debug PA2/3、编码器 EXTI PA4/PB5））
    # **wiki-stm32-batch5 起 PA5 为 ADC 共享组**：本批 8 件（mq2/mq135/mq5/
    # photoresistance/rain/s12sd/soil/gp2y1014au）与 flame 共读 PA5——页面原脚
    # 即共读点（页面 ADC 序列收敛 ml_adc，ml_adc 顺序调用互不干扰）；同一物理
    # 脚只能接一件器件，多件同测需外部分路器/分时切换（mspm0 MEM0 共读同口径）
    "PA5": {
        "motor.MOTOR_B_ENC_DIR",
        "flame.FLAME_AO",
        "mq2.MQ2_AO",
        "mq135.MQ135_AO",
        "mq5.MQ5_AO",
        "photoresistance.PHOTORESISTANCE_AO",
        "rain.RAIN_AO",
        "s12sd.S12SD_AO",
        "soil.SOIL_AO",
        "gp2y1014au.GP2Y1014_AO",
        # wiki-stm32-batch6/01-07：MQ 系收尾 7 件并入 PA5 ADC 共享组
        # （flame + 8 + 7 = 16 ADC 角色同脚——ml_adc 顺序调用无扰；同一物理
        # 脚只能接一件器件，多件同测需外部分路器/分时切换）
        "mq3.MQ3_AO",
        "mq4.MQ4_AO",
        "mq6.MQ6_AO",
        "mq7.MQ7_AO",
        "mq8.MQ8_AO",
        "mq9.MQ9_AO",
        "ms1100.MS1100_AO",
        # wiki-stm32-batch7/01-02：us016/ir_distance 并入 PA5 ADC 共享组——
        # 两测距件**互替件同脚**（同一物理脚只能接一件——互替同脚先例语义：
        # 二选一接入无需另消解；罕见同选经绑定其一换 PA0/PA1）
        "us016.US016_AO",
        "ir_distance.IR_DISTANCE_AO",
    },
    # ttp224 默认 PB12-15 与 config DIP0-3 + pid GRAY_D1-4 重叠（触摸按键≠
    # 拨码配置/巡线灰度；四脚同口约束——换口需整组迁移，同选经引脚绑定消解）
    # **wiki-stm32-batch7/05**：key_matrix ROW1-4 并入 PB12-15——矩阵键盘
    # （机械）与 ttp224（触摸 4 键）**互替件同脚先例**（二选一接入无需另
    # 消解；与 DIP/GRAY 不同框、同选概率最低，同选经引脚绑定消解）
    "PB12": {
        "pid.GRAY_D1",
        "config.DIP0",
        "ttp224.TTP224_OUT1",
        "key_matrix.KEY_MATRIX_ROW1",
        # wiki-stm32-batch8/03：nrf24l01 CSN——2.4G 无线与拨码/灰度/触摸/矩阵
        # 输入不同框、同选概率最低（无线链路常用脚避开人机输入组合）
        "nrf24l01.NRF24L01_CSN",
    },
    "PB13": {
        "pid.GRAY_D2",
        "config.DIP1",
        "ttp224.TTP224_OUT2",
        "key_matrix.KEY_MATRIX_ROW2",
        # wiki-stm32-batch8/03：nrf24l01 CE——与 CSN 同策略
        "nrf24l01.NRF24L01_CE",
    },
    "PB14": {
        "pid.GRAY_D3",
        "config.DIP2",
        "ttp224.TTP224_OUT3",
        "key_matrix.KEY_MATRIX_ROW3",
    },
    "PB15": {
        "pid.GRAY_D4",
        "config.DIP3",
        "ttp224.TTP224_OUT4",
        "key_matrix.KEY_MATRIX_ROW4",
    },
    # hx711 称重默认 SCK=PB5 / DT=PB0（wiki-stm32-batch3/07）：PB5 与电机
    # 编码器 A 相 MOTOR_A_ENC 重叠（光电编码器闭环小车与静态称重/电子秤
    # 不同框）；PB0 与 TB6612 B 相方向 MOTOR_B_DIR 重叠（电机方向与称重
    # 不同框）——刻意不叠采集类/声光件（称重+传感站/报警常见组合），
    # 同选经引脚绑定消解
    # **wiki-stm32-batch5/08**：gp2y1014au LED 驱动（器件必需——低有效脉冲）
    # 默认 PB5（页面原脚 PA2=DEBUG_UART TX 不照抄）——粉尘与称重/光电编码器
    # 闭环不同框、同选概率最低，同选经引脚绑定消解
    # **wiki-stm32-batch7/04**：ec11 B 相并入 PB5——EC11 人机旋钮与称重/光电
    # 编码器闭环不同框（轮询不占 EXTI——PB5 线 5 与 MOTOR_A_ENC 同线同脚
    # 正交共享），同选经引脚绑定消解
    "PB5": {
        "motor.MOTOR_A_ENC",
        "hx711.HX711_SCK",
        "gp2y1014au.GP2Y1014_LED",
        "ec11.EC11_B",
        # wiki-stm32-batch8/03：nrf24l01 IRQ（轮询只读）——2.4G 无线与编码器/
        # 旋钮/称重/粉尘不同框、同选概率最低；本件不注册 EXTI（与编码器线
        # 共享正交、EXTI 门禁默认组合不拦）
        "nrf24l01.NRF24L01_IRQ",
        # wiki-stm32-batch8/04：rc522 MISO——读卡与编码器/旋钮/称重/粉尘
        # 不同框、同选概率最低
        "rc522.RC522_MISO",
        # wiki-stm32-batch9/03：fingerprint TOUCH——指纹门禁与「带编码器闭环
        # 小车/称重/粉尘」不同框、同选概率最低（页面 PA1 不照抄），同选经
        # 引脚绑定消解
        "fingerprint.FINGERPRINT_TOUCH",
    },
    "PB0": {
        "motor.MOTOR_B_DIR",
        "hx711.HX711_DT",
        "ec11.EC11_SW",
        # wiki-stm32-batch8/04：rc522 CS——读卡与电机方向/称重/旋钮不同框
        "rc522.RC522_CS",
    },
    # ds18b20 默认 PB1 与 MOTOR_B_DIR2 重叠（wiki-stm32-batch4/04：测温与
    # 单电机方向不同框、同选概率最低；页面默认 PB0 不采用 = MOTOR_B_DIR；
    # 单总线件不叠软 I2C 总线件与传感站/声光组合）
    # **wiki-stm32-batch8/04**：rc522 RST 并入 PB1——读卡与测温/电机方向不同框
    "PB1": {
        "motor.MOTOR_B_DIR2",
        "ds18b20.DS18B20_DATA",
        "rc522.RC522_RST",
    },
    # PA15 蜂鸣器组（wiki-stm32-batch9/01：jq8900 语音播报并入 PA15——语音播报
    # 与蜂鸣器为**提示输出互替**（替代而非组合）、同选概率最低（互替同脚先例：
    # ttp224×key_matrix），同选经引脚绑定消解；PA15 = JTDI 复用脚，作 GPIO 需
    # SWJ_CFG 释放 JTAG（保留 SWD）——key(PB3)/relay/hc05(PB4) 先例同一约束）
    "PA15": {
        "config.BUZZER",
        "jq8900.JQ8900_TX",
    },
    # PC14 黄灯组（wiki-stm32-batch9/02：syn6288 语音合成并入 PC14——语音播报
    # 与板载指示灯为**输出指示互替**（替代而非组合）、同选概率最低；与
    # jq8900（PA15）刻意错开（语音两件常同选、默认即不撞），同选经绑定消解）
    "PC14": {
        "config.LED_YELLOW",
        "syn6288.SYN6288_TX",
    },
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
        "at24c02.AT24C02_SCL",
        "ags10.AGS10_SCL",
        "ads1115.ADS1115_SCL",
        "tcs34725.TCS34725_SCL",
        "mlx90614.MLX90614_SCL",
        "sgp30.SGP30_SCL",
        "pca9685.PCA9685_SCL",
        "bmp180.BMP180_SCL",
        "ms5611.MS5611_SCL",
        # wiki-stm32-batch9/04：l298n IN1——**物理冲突 ⚠ 登记**（PWM 输出 ×
        # I2C SCL/SDA 总线同脚分属不同外设——l298n×I2C 件同选时前端标 ⚠ +
        # 绑定消解；与 TB6612 motor 互替刻意错开 TIM/脚；TIM 门禁默认×默认
        # 不拦现状口径）
        "l298n.L298N_IN1",
    },
    "PA7": {
        "motor.MOTOR_A_DIR2",
        "aht10.AHT10_SDA",
        "bh1750.BH1750_SDA",
        "sht20.SHT20_SDA",
        "sht30.SHT30_SDA",
        "at24c02.AT24C02_SDA",
        "ags10.AGS10_SDA",
        "ads1115.ADS1115_SDA",
        "tcs34725.TCS34725_SDA",
        "mlx90614.MLX90614_SDA",
        "sgp30.SGP30_SDA",
        "pca9685.PCA9685_SDA",
        "bmp180.BMP180_SDA",
        "ms5611.MS5611_SDA",
        # wiki-stm32-batch9/04：l298n IN2——同上（物理冲突 ⚠ 登记 + 绑定消解）
        "l298n.L298N_IN2",
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
    assert grouped["PB0"] == {
        "motor.MOTOR_B_DIR",
        "hx711.HX711_DT",
        "ec11.EC11_SW",
        "rc522.RC522_CS",
    }
    assert grouped["PA2"] == {"debug_uart.DEBUG_UART_TX"}
    assert grouped["PA3"] == {"debug_uart.DEBUG_UART_RX"}
    assert grouped["PC13"] == {"config.LED_RED"}
    assert grouped["PC14"] == {
        "config.LED_YELLOW",
        "syn6288.SYN6288_TX",
    }
    assert grouped["PC15"] == {"config.LED_GREEN"}
    # wiki-stm32-batch8/01：as32 并入 PB10/PB11（与 Zigbee 无线数传**互替件
    # 同脚先例**——门禁只查用户绑定，默认共享合法先例）
    assert grouped["PB10"] == {
        "zigbee_uart.ZIGBEE_UART_TX",
        "zigbee_uart_key.ZIGBEE_UART_TX",
        "zigbee_link.ZIGBEE_UART_TX",
        "key_matrix.KEY_MATRIX_COL3",
        "as32.AS32_UART_TX",
        "nrf24l01.NRF24L01_CLK",
    }
    assert grouped["PB11"] == {
        "zigbee_uart.ZIGBEE_UART_RX",
        "zigbee_uart_key.ZIGBEE_UART_RX",
        "zigbee_link.ZIGBEE_UART_RX",
        "key_matrix.KEY_MATRIX_COL4",
        "as32.AS32_UART_RX",
        "nrf24l01.NRF24L01_MOSI",
    }
