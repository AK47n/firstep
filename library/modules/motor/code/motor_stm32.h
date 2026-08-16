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
