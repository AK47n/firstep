/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《SG90舵机》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/sg90-steering-engine.html
 * （批 11 C 类核对：本件 = 语义同源页面——50Hz/0.5-2.5ms/0-180° 逐项吻合；
 * 16 路舵机 PCA9685 页对应库内 pca9685 模块——见 manifest notes）；
 * 使用 / 复制 / 修改 / 传播请遵循立创版权要求。
 */
#ifndef SERVO_H
#define SERVO_H

#include <stdint.h>

/* 舵机角度控制（双平台对偶 API，b1-adc-servo/02）：
 *   servo_init(servo_id, channel)     初始化（50Hz/20ms 周期，舵机归 0°）
 *   servo_set_angle(servo_id, angle)  角度 0-180（越界钳位到端点）
 * 引脚由生成器绑定（stm32 pin_config.h 宏 / mspm0 syscfg ccp0Pin），
 * 模块代码不吃引脚字面量。 */

/* 角度 → 脉宽换算常量（**单源**，工单 b1-adc-servo/02）：
 * SG90 类舵机 50Hz（20ms 周期），脉宽 0.5ms(0°) ~ 2.5ms(180°) 线性映射。
 * 两个平台的 .c 只做「脉宽 → 定时器计数值」的比例换算，角度换算的常量
 * 一律取自本文件——换舵机规格只改这里，不再两处各硬编码一套。
 * 平台侧满量程仍由平台单源提供（stm32 = 母版 ml_pwm.h MAX_DUTY；
 * mspm0 = 运行时算出的周期计数值）。 */
#define SERVO_FREQ_HZ       50u                            /* 控制频率 */
#define SERVO_PERIOD_US     (1000000u / SERVO_FREQ_HZ)     /* 周期 20ms */
#define SERVO_ANGLE_MAX     180u                           /* 角度满量程 */
#define SERVO_MIN_PULSE_US  500u                           /* 0° 脉宽 */
#define SERVO_MAX_PULSE_US  2500u                          /* 180° 脉宽 */
#define SERVO_PULSE_SPAN_US (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)

/* SERVO_PULSE_US(angle)：角度 → 脉宽（微秒）。分子一次算完再除，避免
 * 「先除再乘」的累计截断误差；angle 越界由调用方按 SERVO_ANGLE_MAX 钳位。 */
#define SERVO_PULSE_US(angle)                                              \
    ((SERVO_MIN_PULSE_US * SERVO_ANGLE_MAX                                 \
      + (uint32_t)(angle) * SERVO_PULSE_SPAN_US) / SERVO_ANGLE_MAX)

void servo_init(uint8_t servo_id, uint8_t channel);
void servo_set_angle(uint8_t servo_id, uint16_t angle);

#endif
