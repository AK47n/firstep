#ifndef MOTOR_H
#define MOTOR_H

#include "ti_msp_dl_config.h"
#include <stdint.h>

// 编码器线数
#define MOTOR_BIANMAQI 260
// 轮胎直径 mm
#define MOTOR_WHEEL_D 48

// G3507      TB6612
// PB9 <--> AIN1
// PA18 <--> AIN2
// PA12 <--> PWMA
// GND <--> GND
// 3V3 <--> VCC
// 3V3 <--> STBY  (硬件直连，不再由MCU控制)

// TB6612    电源模块
// VM          7.4V
// GND         GND

// TB6612    直流电机1
// AO1<--> M+
// AO2<--> M-

// G3507    直流电机1
// PA16 <--> A (编码器1A)
// PA17 <--> B (编码器1B)
// 3V3 <--> VCC
// GND <--> GND

// 直流电机接线：
// BO1<--> M+
// BO2<--> M-
// PB19 <--> A
// PB20 <--> B
// 3V3 <--> VCC
// GND <--> GND

// G3507    TB6612
// PA13 <--> PWMB
// PA7 <--> BIN2
// PB18 <--> BIN1

// 所有的GND都需要连接在一起

void motor_init(uint8_t motor_id);
void motor_set_duty(uint8_t motor_id, uint32_t duty);
void motor_set_direction(uint8_t motor_id, uint8_t direction);
int limit_duty(int duty);

/* 读左右轮编码器脉冲计数并清零（GROUP1_IRQHandler 累加；速度换算由调用方
 * 按采样周期完成，线数 / 轮径见上方宏） */
void motor_encoder_read(int32_t *left, int32_t *right);

#endif // MOTOR_H
