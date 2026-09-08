/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《TB6612电机驱动模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/tb6612-motor-drive-module.html
 * （批 11 C 类核对：本件 = 页面功能超集——PWM 双路 + 编码器；对照结论见
 * manifest notes）；使用 / 复制 / 修改 / 传播请遵循立创版权要求。
 */
#ifndef _MOTOR_STM32_H
#define _MOTOR_STM32_H

#include "headfile.h"
#include <stdint.h>

void motor_init(void);
void motorA_duty(int duty);
void motorB_duty(int duty);
void encoder_init(void);

// 统一 API（与 mspm0 侧 motor.h 同名同义）：
//   motor_set_duty(id, duty)        duty = PWM 原始占空比（stm32 母版 0~50000）
//   motor_set_direction(id, dir)    dir: 0 停 / 1 正转 / 2 反转
//   motor_encoder_read(left, right) 读左右轮编码器计数并清零
void motor_set_duty(uint8_t motor_id, uint32_t duty);
void motor_set_direction(uint8_t motor_id, uint8_t direction);
void motor_encoder_read(int32_t *left, int32_t *right);

extern int Encoder_count1, Encoder_count2;
extern int speed_now;
extern uint8_t motorA_dir, motorB_dir;

#endif
