#ifndef PCA9685_H
#define PCA9685_H

#include <stdint.h>

/* PCA9685 16 路舵机/PWM 驱动（mspm0，纯驱动切片，ADR 0009）：软 I2C 位操作
 * 2 脚（SCL/SDA，照 AHT10 先例不占硬件 I2C 外设），芯片内部 25MHz 振荡器
 * 生成 16 路 PWM（主控只写寄存器，不占 TIMER）——`pca9685_init(freq_hz)`
 * 设频率 + 16 路归零、`pca9685_set_pwm(ch, width)` 写 12bit 计数（ON=0）、
 * `pca9685_set_angle(ch, angle)` 0-180° ↔ 0.5-2.5ms 脉宽（**与库内 servo 模块
 * 同一口径**——servo 是 TIMG8 硬件 PWM 单路，本模块是 16 路 I2C 寄存器扩展，
 * 二者互补：单舵机用 servo、多舵机/机械臂用 pca9685）。
 * 引脚 = 母版 syscfg 实例 PCA9685：SCL（输出，默认 PB6）/ SDA（双向，默认
 * PB7——与 STEP_MOTOR/HUIDU/AHT10/DHT11 默认重叠，同选时经引脚绑定消解；
 * 软 I2C 需板上/模块自带上拉）。SDA 方向运行时切换（写 = 输出，读 ACK/
 * 数据 = 输入）。
 * 协议（PCA9685 数据手册）：I2C 从地址 = 0x40 + A5..A0（写 = 地址<<1，
 * 默认 A5..A0=0 → 0x80 写 / 0x81 读；页面「62 个驱动板挂单总线」即 6 位
 * 地址线选择）；MODE1=0x00，频率 PRE_SCALE=0xFE 按
 * prescale = round(25000000/(4096×freq))-1（改频率须先置 SLEEP 位）；
 * LEDn_ON_L/H + LEDn_OFF_L/H（0x06+4n..0x09+4n）各 12bit，计数 0x000-0xFFF
 * 循环，OFF ≤ ON = 输出电平保持；ON=0/OFF=width 即脉宽（width=4096 = 100%
 * 常亮）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/control--16-ch-servo-drive-module.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 main.c 演示与
 * printf、函数名规范化、IIC 原语收敛为模块内静态、delay_1ms → delay 模块、
 * 页面 FLOOR Excel 注解剔除、角度映射按 servo 同口径修正）。 */

#define PCA9685_DEFAULT_FREQ_HZ 50u /* 标准舵机时基（20ms 周期） */

/* pca9685_init：复位 MODE1（0x00——页面「没有这步不工作」）+ 设频率
 * （prescale 睡眠-写-唤醒）+ 16 路 PWM 归零；此后可 set_pwm/set_angle。 */
void pca9685_init(uint16_t freq_hz);

/* pca9685_set_pwm：通道 0-15 写脉宽（12bit 计数，ON=0；0-4095 + 4096 =
 * 常亮）。 */
void pca9685_set_pwm(uint8_t channel, uint16_t width);

/* pca9685_set_angle：通道 0-15 写舵机角度 0-180（越界钳位；0.5-2.5ms 脉宽
 * 按当前频率换算计数——50Hz 下 102.4-512 tick，与 servo 模块同口径）。 */
void pca9685_set_angle(uint8_t channel, uint8_t angle);

/* pca9685_set_freq：运行中重设全板 PWM 频率（全板 16 路同频率；50Hz 舵机
 * 标准值见 PCA9685_DEFAULT_FREQ_HZ）。 */
void pca9685_set_freq(uint16_t freq_hz);

/* pca9685_set_address：I2C 地址选择（A5..A0 = 0-0x3F，默认 0；写地址 =
 * (0x40 + A5..A0) << 1，最多 62 板同总线级联）。 */
void pca9685_set_address(uint8_t a5);

#endif /* PCA9685_H */
