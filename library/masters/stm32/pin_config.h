#ifndef __PIN_CONFIG_H
#define __PIN_CONFIG_H

/* ============================================================
 * 电机引脚集中配置（值 = 2021F 真机原值，21F code/motor.c + user/isr.c）
 *
 * 改引脚只动本文件（对偶 mspm0 侧 SysConfig 生成的 DC_MOTOR_* 宏）：
 * motor 模块的 code/motor_stm32.c / pid 模块的 code/pid_isr.c 只引用
 * 这些宏、不写死引脚字面量。
 *
 * ⚠️ EXTI 中断名绑定引脚线号：PA2 → EXTI2_IRQHandler、PA4 →
 * EXTI4_IRQHandler 固定，编码器线一换，对应 handler 名也要换（中断
 * 代码整体留在模块内可替换位置）。
 * ============================================================ */

/* ---- PWM（电机调速，频率 1000Hz = 21F 原值）---- */
#define MOTOR_A_PWM_TIM     TIM_2
#define MOTOR_A_PWM_CH      TIM2_CH1   /* PA0 */
#define MOTOR_B_PWM_TIM     TIM_2
#define MOTOR_B_PWM_CH      TIM2_CH2   /* PA1 */
#define MOTOR_PWM_FREQ      1000

/* ---- 方向（TB6612 AIN1/AIN2、BIN1/BIN2，21F 原值）---- */
#define MOTOR_A_DIR_PORT    GPIO_A
#define MOTOR_A_DIR_PIN     Pin_6
#define MOTOR_A_DIR2_PORT   GPIO_A
#define MOTOR_A_DIR2_PIN    Pin_7
#define MOTOR_B_DIR_PORT    GPIO_B
#define MOTOR_B_DIR_PIN     Pin_0
#define MOTOR_B_DIR2_PORT   GPIO_B
#define MOTOR_B_DIR2_PIN    Pin_1

/* ---- 编码器（EXTI 脉冲计数 + 方向输入，21F 原值）---- */
#define MOTOR_A_ENC_EXTI      EXTI_PA2   /* PA2，下降沿触发 */
#define MOTOR_A_ENC_LINE      2          /* EXTI2_IRQHandler 的线号 */
#define MOTOR_A_ENC_DIR_PORT  GPIO_A
#define MOTOR_A_ENC_DIR_PIN   Pin_3      /* 方向输入（上拉） */
#define MOTOR_B_ENC_EXTI      EXTI_PA4   /* PA4，下降沿触发 */
#define MOTOR_B_ENC_LINE      4          /* EXTI4_IRQHandler 的线号 */
#define MOTOR_B_ENC_DIR_PORT  GPIO_A
#define MOTOR_B_ENC_DIR_PIN   Pin_5      /* 方向输入（上拉） */

#endif /* __PIN_CONFIG_H */
