"""mspm0 syscfg 实例 ↔ 消费模块映射（单源表，工单 syscfg-prune/01 起）。

母版 mspm0.syscfg = 全量实例（默认布局理论上限）。两个消费方：
- syscfg_prune：生成时按选中模块裁剪（未选模块实例不落盘）。
- pin_bindings / pinwriter：默认重叠布局（STEP_MOTOR SLP2/DIR2 与
  HUIDU R3/R4 同 PB6/PB7）的槽位定位按「实例路径」区分——同一默认值多行时，
  GPIO 组角色用本表反查该模块消费的实例名来选唯一落点。
"""

from __future__ import annotations

# 实例名 → 消费模块 slug 元组。任一消费模块被选中即保留；全部未选才裁剪。
# 共享实例：DC_MOTOR 只归 motor（编码器计数已从 key 迁入 motor，
# module-dep-cleanup/02），HUIDU 由 huidu/pid(mspm0 GRAY_D1-8)/xunji
# 共用（灰度槽位）；DIGIT_UART 由 digit_uart/coord_detect 共用（K230 视觉），
# ZIGBEE_UART 由 zigbee_uart（收）/zigbee_uart_key（发）/zigbee_link 共用
# （同一路 RX 单消费者——zigbee_uart 与 zigbee_link 硬互斥）；
# HC05_UART 与 DEBUG_UART/UWB_UART 同属 UART2 外设的候选宿主（HC05 9600 独立
# 波特率）——2026-09-05 SysConfig CLI 实证：同一 UART 外设多实例是 SysConfig
# 级 Resource conflict（"UART2 is already in use by DEBUG_UART"；UART 实例
# 上限 4=外设数），生成前裁剪保证每工程至多一个实例——「共享」实为裁剪后
# 独占（批次 1 仅单选编译实证，从未多实例同选）；同选且未换实例 = SysConfig
# 生成失败，消解 = 引脚绑定换实例（其余 UART0/1/3 同样被占，先例 DEBUG+UWB）。
# FINGERPRINT_UART 默认 UART0（与 IMU601 同外设默认，同选时经引脚绑定换实例
# 消解，_receive_response 轮询无 IRQHandler）；语音模块（jq8900/syn6288）
# 走软 UART 单发 TX（GPIO 位操作，不占 UART 实例）。
INSTANCE_CONSUMERS: dict[str, tuple[str, ...]] = {
    "PWMAB": ("motor",),
    "DCC_100_PWM2": ("step_motor",),
    "MOTOR_PID": ("pid",),
    "NTB": ("ntb_time",),
    "DC_MOTOR": ("motor",),
    "HUIDU": ("huidu", "pid", "xunji"),
    "KEY": ("key",),
    "IR_BEAM": ("ir_beam",),
    "WS2812": ("ws2812",),
    "HX711": ("hx711",),
    "AHT10": ("aht10",),
    "ADS1115": ("ads1115",),
    "TCS34725": ("tcs34725",),
    "MLX90614": ("mlx90614",),
    "AT24C02": ("at24c02",),
    "DHT11": ("dht11",),
    "DS18B20": ("ds18b20",),
    "SHT30": ("sht30",),
    "BH1750": ("bh1750",),
    "SR04": ("sr04",),
    "JOYSTICK": ("joystick",),
    "HC05": ("hc05",),
    "NRF24L01": ("nrf24l01",),
    "IR_REMOTE": ("ir_remote",),
    "MAX7219": ("max7219",),
    "PCA9685": ("pca9685",),
    "IR_TX": ("ir_remote_tx",),
    "JQ8900": ("jq8900",),
    "SYN6288": ("syn6288",),
    "RC522": ("rc522",),
    "LED_BEEP": ("led",),
    "STEP_MOTOR": ("step_motor",),
    "IMU601": ("imu_uart",),
    "DIGIT_UART": ("digit_uart", "coord_detect"),
    "DEBUG_UART": ("debug_uart",),
    "UWB_UART": ("uwb_uart",),
    "HC05_UART": ("hc05",),
    "FINGERPRINT_UART": ("fingerprint",),
    "FINGERPRINT": ("fingerprint",),
    "ZIGBEE_UART": ("zigbee_uart", "zigbee_uart_key", "zigbee_link"),
    "OLED": ("oled",),
    "I2C_0": ("ml_mpu6050",),
    "ADC12_0": ("adc", "joystick", "us016", "ir_distance", "mq2"),
    "SERVO_PWM": ("servo",),
}

# slug → 该模块 GPIO 角色可能落脚的实例名元组（INSTANCE_CONSUMERS 反转）。
INSTANCES_BY_SLUG: dict[str, tuple[str, ...]] = {}
for _instance, _slugs in INSTANCE_CONSUMERS.items():
    for _slug in _slugs:
        INSTANCES_BY_SLUG.setdefault(_slug, ())
        if _instance not in INSTANCES_BY_SLUG[_slug]:
            INSTANCES_BY_SLUG[_slug] += (_instance,)
