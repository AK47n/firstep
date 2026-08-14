#ifndef MOTOR_H
#define MOTOR_H

#define PI 3.14

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

#include "ti_msp_dl_config.h"
#include "huidu.h"
#include "imu.h"
#include "led_beep.h"
#include "ntb_time.h"

void motor_init(uint8_t motor_id);
void motor_set_duty(uint8_t motor_id, uint32_t duty);
void motor_set_direction(uint8_t motor_id, uint8_t direction);
int limit_duty(int duty);

/**
 * @brief 电机自检：依次测试电机1/2的正反转
 *
 * @note 测试流程（每步2秒，OLED显示状态）：
 *       1. 电机1正转 → 2. 电机1反转
 *       3. 电机2正转 → 4. 电机2反转
 *       5. 全部停止，测试结束
 *       如果某步电机不转，检查该路接线
 */
void motor_test(void);

/**
 * @brief 编码器自检：电机1/2正转5秒，OLED实时显示计数值
 *
 * @note 测试前需确保编码器 A/B 相接好：
 *       电机1：PA16(A) PA17(B)
 *       电机2：PB19(A) PB20(B)
 *       两个电机的 count 应持续增长、数值相近
 */
void encoder_test(void);

/**
 * @brief PID 调参测试：以目标速度运行，OLED 显示实时速度
 *
 * @param target_mm_s 目标速度 (mm/s)，建议 300~800
 *
 * @note 调整 motor.c 中的 kp/ki 变量后烧录观察响应
 */
void pid_tuning(uint16_t target_mm_s);

#endif // MOTOR_H
