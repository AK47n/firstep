#ifndef SERVO_H
#define SERVO_H

#include <stdint.h>

/* 舵机角度控制（双平台对偶 API，b1-adc-servo/02）：
 *   servo_init(servo_id, channel)     初始化（50Hz/20ms 周期，舵机归 0°）
 *   servo_set_angle(servo_id, angle)  角度 0-180（越界钳位到端点）
 * 引脚由生成器绑定（stm32 pin_config.h 宏 / mspm0 syscfg ccp0Pin），
 * 模块代码不吃引脚字面量。 */

void servo_init(uint8_t servo_id, uint8_t channel);
void servo_set_angle(uint8_t servo_id, uint16_t angle);

#endif
