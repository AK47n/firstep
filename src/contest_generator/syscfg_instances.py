"""mspm0 syscfg 实例 ↔ 消费模块映射（单源表，工单 syscfg-prune/01 起）。

母版 mspm0.syscfg = 全量实例（默认布局理论上限）。两个消费方：
- syscfg_prune：生成时按选中模块裁剪（未选模块实例不落盘）。
- pin_bindings / pinwriter：默认重叠布局（STEP_MOTOR SLP2/DIR2 与
  HUIDU R3/R4 同 PB6/PB7）的槽位定位按「实例路径」区分——同一默认值多行时，
  GPIO 组角色用本表反查该模块消费的实例名来选唯一落点。
"""

from __future__ import annotations

# 实例名 → 消费模块 slug 元组。任一消费模块被选中即保留；全部未选才裁剪。
# 共享实例：DC_MOTOR 由 motor/key 共用（编码器中断在 key），HUIDU 由
# huidu/pid(mspm0 GRAY_D1-8)/xunji 共用（灰度槽位）。
INSTANCE_CONSUMERS: dict[str, tuple[str, ...]] = {
    "PWMAB": ("motor",),
    "DCC_100_PWM2": ("step_motor",),
    "MOTOR_PID": ("motor", "pid"),
    "NTB": ("ntb_time",),
    "DC_MOTOR": ("motor", "key"),
    "HUIDU": ("huidu", "pid", "xunji"),
    "KEY": ("key",),
    "LED_BEEP": ("led_beep",),
    "STEP_MOTOR": ("step_motor",),
    "IMU601": ("imu_uart",),
    "DIGIT_UART": ("digit_uart", "ball_detect"),
    "OLED": ("oled",),
    "I2C_0": ("ml_mpu6050",),
}

# slug → 该模块 GPIO 角色可能落脚的实例名元组（INSTANCE_CONSUMERS 反转）。
INSTANCES_BY_SLUG: dict[str, tuple[str, ...]] = {}
for _instance, _slugs in INSTANCE_CONSUMERS.items():
    for _slug in _slugs:
        INSTANCES_BY_SLUG.setdefault(_slug, ())
        if _instance not in INSTANCES_BY_SLUG[_slug]:
            INSTANCES_BY_SLUG[_slug] += (_instance,)
