#include "motor_stm32.h"
#include "pin_config.h"

uint8_t motorA_dir = 0; // 1 为正转 0 为反转
uint8_t motorB_dir = 0; // 1 为正转 0 为反转

int Encoder_count1 = 0;
int Encoder_count2 = 0;

int speed_now;

void motor_init()
{
    pwm_init(MOTOR_A_PWM_TIM, MOTOR_A_PWM_CH, MOTOR_PWM_FREQ);
    gpio_init(MOTOR_A_DIR_PORT, MOTOR_A_DIR_PIN, OUT_PP);
    gpio_init(MOTOR_A_DIR2_PORT, MOTOR_A_DIR2_PIN, OUT_PP);

    pwm_init(MOTOR_B_PWM_TIM, MOTOR_B_PWM_CH, MOTOR_PWM_FREQ);
    gpio_init(MOTOR_B_DIR_PORT, MOTOR_B_DIR_PIN, OUT_PP);
    gpio_init(MOTOR_B_DIR2_PORT, MOTOR_B_DIR2_PIN, OUT_PP);
}

void motorA_duty(int duty)
{
    pwm_update(MOTOR_A_PWM_TIM, MOTOR_A_PWM_CH, duty);
    gpio_set(MOTOR_A_DIR_PORT, MOTOR_A_DIR_PIN, motorA_dir);
    gpio_set(MOTOR_A_DIR2_PORT, MOTOR_A_DIR2_PIN, !motorA_dir);
}

void motorB_duty(int duty)
{
    pwm_update(MOTOR_B_PWM_TIM, MOTOR_B_PWM_CH, duty);
    gpio_set(MOTOR_B_DIR_PORT, MOTOR_B_DIR_PIN, motorB_dir);
    gpio_set(MOTOR_B_DIR2_PORT, MOTOR_B_DIR2_PIN, !motorB_dir);
}

void encoder_init()
{
    exti_init(MOTOR_A_ENC_EXTI, FALLING, 0);
    gpio_init(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN, IU);

    exti_init(MOTOR_B_ENC_EXTI, FALLING, 0);
    gpio_init(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN, IU);
}

// 编码器脉冲计数中断（中断跟着功能模块走——选 motor 即带计数，先例 =
// mspm0 key 模块自带 GROUP1_IRQHandler）。handler 名绑定引脚线号
// （PA2 固定 EXTI2、PA4 固定 EXTI4），换编码器引脚需整体替换对应 handler
// （线号宏在 pin_config.h，与 handler 名一一对应）。
void EXTI2_IRQHandler(void)
{
    if (EXTI->PR & (1 << MOTOR_A_ENC_LINE))
    {
        if (gpio_get(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN))
            Encoder_count1++;
        else
            Encoder_count1--;
        EXTI->PR = 1 << MOTOR_A_ENC_LINE;
    }
}

void EXTI4_IRQHandler(void)
{
    if (EXTI->PR & (1 << MOTOR_B_ENC_LINE))
    {
        if (gpio_get(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN))
            Encoder_count2++;
        else
            Encoder_count2--;
        EXTI->PR = 1 << MOTOR_B_ENC_LINE;
    }
}
