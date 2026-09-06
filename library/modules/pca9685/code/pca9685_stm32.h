/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《16路舵机驱动模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/16-ch-servo-drive-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef PCA9685_STM32_H
#define PCA9685_STM32_H

#include <stdint.h>

/* PCA9685 16 路舵机/PWM 驱动（stm32，纯驱动切片，ADR 0009）：软 I2C 位操作
 * 2 脚（SCL/SDA，照 AHT10 先例不占硬件 I2C 外设），芯片内部 25MHz 振荡器
 * 生成 16 路 PWM（主控只写寄存器，不占 TIMER）——`pca9685_init(freq_hz)`
 * 设频率 + 16 路归零、`pca9685_set_pwm(ch, width)` 写 12bit 计数（ON=0）、
 * `pca9685_set_angle(ch, angle)` 0-180° ↔ 0.5-2.5ms 脉宽（**与库内 servo
 * 模块同一口径**——servo 是硬件 PWM 单路，本模块是 16 路 I2C 寄存器扩展，
 * 二者互补：单舵机用 servo、多舵机/机械臂用 pca9685）。API 与 mspm0 版
 * 完全对齐（同函数名/同签名/同语义——chip 内部振荡，零 MCU 位时序）。
 * 引脚 = pin_config.h 单源 PCA9685_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——与批次 2 六件共挂同一软 I2C 总线；**⚠️ 默认地址 0x40 ×
 * 批次 2 sht20 0x40 同址**：同选时 pca9685_set_address(1)（0x41，A5 接线）
 * 或绑定换独立总线（sht20 地址不可改）——notes 明示，不强制裁决；
 * 与 motor MOTOR_A_DIR/DIR2 默认重叠：16 路舵机驱动与「带电机方向的小车
 * 运动控制」不同框、同选概率最低，同选经引脚绑定消解；页面默认 SDA=PA5/
 * SCL=PA6 不采用 = flame/总线腳占用）。
 * **SCL 输出方向初始化（批次 3 回修口径）**：init 必须
 * gpio_init(PCA9685_SCL_GPIO, PCA9685_SCL_PIN, OUT_OD) + 置高——F1 复位后
 * GPIO 为浮空输入，ODR 写入无效（批次 2 SCL 未初始化教训，防回潮守卫）。
 * 协议（PCA9685 数据手册）：I2C 从地址 = 0x40 + A5..A0（写 = 地址<<1，
 * 默认 A5..A0=0 → 0x80 写 / 0x81 读；页面「62 个驱动板挂单总线」即 6 位
 * 地址线选择）；MODE1=0x00，频率 PRE_SCALE=0xFE 按
 * prescale = round(25000000/(4096×freq))-1（改频率须先置 SLEEP 位）；
 * LEDn_ON_L/H + LEDn_OFF_L/H（0x06+4n..0x09+4n）各 12bit，计数 0x000-0xFFF
 * 循环，OFF ≤ ON = 输出电平保持；ON=0/OFF=width 即脉宽（width=4096 = 100%
 * 常亮）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/control--16-ch-servo-drive-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去掉 main.c 演示与
 * printf、函数名规范化、IIC 原语收敛为模块内静态、delay_1ms → delay 模块、
 * 页面 FLOOR Excel 注解剔除、角度映射按 servo 同口径修正。**页面缺陷修正
 * 清单（notes + 守卫）**：① **两套角度映射不一致**（setAngle 158+angle*2.2
 * vs Init 145+angle*2.4）→ 统一照 mspm0（0.5-2.5ms 脉宽→0-180° 单式）；
 * ② main 60Hz vs 正文 50Hz → 默认 50Hz（PCA9685_DEFAULT_FREQ_HZ）；
 * ③ delay_1ms(5)/(100) 库内无 → delay_ms；④ NACK 全丢 → wait_ack 超时
 * 内部发停止（void API 无失败码，mspm0 同款）；⑤ 正文频率公式 (50+1)
 * 错误（代码正确——按代码记录）；⑥ Excel FLOOR 注释污染（不落）；
 * ⑦ 页面直接控角度（API 保留 set_pwm+set_angle 两级——角度层归一、PWM 层
 * 透传，同 mspm0）。 */

#define PCA9685_DEFAULT_FREQ_HZ 50u /* 标准舵机时基（20ms 周期） */

/* pca9685_init：引脚配置（SCL/SDA OUT_OD + 置高——批次 3 回修口径）+ 复位
 * MODE1（0x00——页面「没有这步不工作」）+ 设频率（prescale 睡眠-写-唤醒）+
 * 16 路 PWM 归零；此后可 set_pwm/set_angle。 */
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
 * (0x40 + A5..A0) << 1，最多 62 板同总线级联）——**sht20 同址 0x40 冲突时
 * 靠此改址（set_address(1) = 0x41）或绑定换独立总线**。 */
void pca9685_set_address(uint8_t a5);

#endif /* PCA9685_STM32_H */
