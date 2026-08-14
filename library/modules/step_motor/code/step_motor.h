#ifndef STEP_MOTOR_H
#define STEP_MOTOR_H

/* ===== 脉冲式步进电机驱动（mspm0，纯驱动切片 ADR 0009） =====
 * SysConfig 依赖（实例/宏名与源码一一对应；2026-08-14 起母版默认布局已含
 * 此配置（工单 mspm0-master-dimx/01），无需再自配）：
 *   PWM TimerG 实例 DCC_100_PWM2（TIMG12 C0 通道输出 → 电机 PWM 输入，
 *   clockPrescale 必须为 1——step_set_speed 按 INST_CLK_FREQ/频率 直算周期）
 *   GPIO 输出 STEP_MOTOR_PORT 端口下 4 个宏（四脚同 GPIOB）：
 *   STEP_MOTOR_RST2_PIN / STEP_MOTOR_SLP2_PIN / STEP_MOTOR_DIR2_PIN /
 *   STEP_MOTOR_DCY2_PIN
 */
// 接线（母版 syscfg 地猛星布局；原工程第二路为 PA12 PWM/PA13 DIR/PA14 DCY/
// PA15 SLP/PA16 RST，与母版 PWMAB 冲突故重排，按实际接线改即可）
// PA14 PWM
// PB24 RST
// PB6  SLP
// PB7  DIR
// PB8  DCY

// 一脉冲 0.05625度
// 角速度 = 0.05625度 * 脉冲频率
// 脉冲频率 = 角速度 / 0.05625度
// 30角速度：30 / 0.05625 = 533.33Hz

#include "ti_msp_dl_config.h"

void step_motor_init(void);
void step_motor_dir_set(uint8_t direction, uint8_t stepper_id);
void step_motor_start(uint8_t stepper_id);
void step_set_speed(uint8_t speed, uint8_t stepper_id);
// void step_motor_step_set(uint8_t step, uint8_t stepper_id);
void step_motor_set_angle(uint8_t angle, uint8_t stepper_id);

#endif // STEP_MOTOR_H
