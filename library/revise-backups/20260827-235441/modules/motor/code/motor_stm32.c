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

// ============================================================
// 统一 API（与 mspm0 侧 motor.h 同名同义，工单 module-functionalize/02）
// ============================================================

void motor_set_duty(uint8_t motor_id, uint32_t duty)
{
    if (motor_id == 1) {
        motorA_duty((int)duty);
    } else if (motor_id == 2) {
        motorB_duty((int)duty);
    }
}

void motor_set_direction(uint8_t motor_id, uint8_t direction)
{
    if (direction == 0) {
        motor_set_duty(motor_id, 0); // 停止 = 占空比 0（方向位保持）
        return;
    }
    // 统一语义 1=正转 / 2=反转 → stm32 旧语义 0=正转 / 1=反转
    uint8_t dir = (direction == 1) ? 0 : 1;
    if (motor_id == 1) {
        motorA_dir = dir;
    } else if (motor_id == 2) {
        motorB_dir = dir;
    }
}

void motor_encoder_read(int32_t *left, int32_t *right)
{
    *left = Encoder_count1;
    Encoder_count1 = 0;
    *right = Encoder_count2;
    Encoder_count2 = 0;
}

void encoder_init()
{
    exti_init(MOTOR_A_ENC_EXTI, FALLING, 0);
    gpio_init(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN, IU);

    exti_init(MOTOR_B_ENC_EXTI, FALLING, 0);
    gpio_init(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN, IU);
}

// 编码器脉冲计数中断（中断跟着功能模块走——选 motor 即带计数，先例 =
// mspm0 key 模块自带 GROUP1_IRQHandler）。ADR 0012 起 handler 按
// pin_config.h 的 MOTOR_A/B_ENC_LINE 宏条件编译：线 0-4 各一个
// EXTIN_IRQHandler、线 5-9 共 EXTI9_5_IRQHandler、线 10-15 共
// EXTI15_10_IRQHandler——handler 内按线位分派 A/B 两编码器（异口同线
// 已被生成门禁拦下，同脚共享 = 两计数器同步计数）。换编码器引脚只改
// 绑定，handler 自动跟随。
#if MOTOR_A_ENC_LINE == 0 || MOTOR_B_ENC_LINE == 0
void EXTI0_IRQHandler(void)
{
#if MOTOR_A_ENC_LINE == 0
    if (EXTI->PR & (1 << MOTOR_A_ENC_LINE))
    {
        if (gpio_get(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN))
            Encoder_count1++;
        else
            Encoder_count1--;
        EXTI->PR = 1 << MOTOR_A_ENC_LINE;
    }
#endif
#if MOTOR_B_ENC_LINE == 0
    if (EXTI->PR & (1 << MOTOR_B_ENC_LINE))
    {
        if (gpio_get(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN))
            Encoder_count2++;
        else
            Encoder_count2--;
        EXTI->PR = 1 << MOTOR_B_ENC_LINE;
    }
#endif
}
#endif

#if MOTOR_A_ENC_LINE == 1 || MOTOR_B_ENC_LINE == 1
void EXTI1_IRQHandler(void)
{
#if MOTOR_A_ENC_LINE == 1
    if (EXTI->PR & (1 << MOTOR_A_ENC_LINE))
    {
        if (gpio_get(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN))
            Encoder_count1++;
        else
            Encoder_count1--;
        EXTI->PR = 1 << MOTOR_A_ENC_LINE;
    }
#endif
#if MOTOR_B_ENC_LINE == 1
    if (EXTI->PR & (1 << MOTOR_B_ENC_LINE))
    {
        if (gpio_get(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN))
            Encoder_count2++;
        else
            Encoder_count2--;
        EXTI->PR = 1 << MOTOR_B_ENC_LINE;
    }
#endif
}
#endif

#if MOTOR_A_ENC_LINE == 2 || MOTOR_B_ENC_LINE == 2
void EXTI2_IRQHandler(void)
{
#if MOTOR_A_ENC_LINE == 2
    if (EXTI->PR & (1 << MOTOR_A_ENC_LINE))
    {
        if (gpio_get(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN))
            Encoder_count1++;
        else
            Encoder_count1--;
        EXTI->PR = 1 << MOTOR_A_ENC_LINE;
    }
#endif
#if MOTOR_B_ENC_LINE == 2
    if (EXTI->PR & (1 << MOTOR_B_ENC_LINE))
    {
        if (gpio_get(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN))
            Encoder_count2++;
        else
            Encoder_count2--;
        EXTI->PR = 1 << MOTOR_B_ENC_LINE;
    }
#endif
}
#endif

#if MOTOR_A_ENC_LINE == 3 || MOTOR_B_ENC_LINE == 3
void EXTI3_IRQHandler(void)
{
#if MOTOR_A_ENC_LINE == 3
    if (EXTI->PR & (1 << MOTOR_A_ENC_LINE))
    {
        if (gpio_get(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN))
            Encoder_count1++;
        else
            Encoder_count1--;
        EXTI->PR = 1 << MOTOR_A_ENC_LINE;
    }
#endif
#if MOTOR_B_ENC_LINE == 3
    if (EXTI->PR & (1 << MOTOR_B_ENC_LINE))
    {
        if (gpio_get(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN))
            Encoder_count2++;
        else
            Encoder_count2--;
        EXTI->PR = 1 << MOTOR_B_ENC_LINE;
    }
#endif
}
#endif

#if MOTOR_A_ENC_LINE == 4 || MOTOR_B_ENC_LINE == 4
void EXTI4_IRQHandler(void)
{
#if MOTOR_A_ENC_LINE == 4
    if (EXTI->PR & (1 << MOTOR_A_ENC_LINE))
    {
        if (gpio_get(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN))
            Encoder_count1++;
        else
            Encoder_count1--;
        EXTI->PR = 1 << MOTOR_A_ENC_LINE;
    }
#endif
#if MOTOR_B_ENC_LINE == 4
    if (EXTI->PR & (1 << MOTOR_B_ENC_LINE))
    {
        if (gpio_get(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN))
            Encoder_count2++;
        else
            Encoder_count2--;
        EXTI->PR = 1 << MOTOR_B_ENC_LINE;
    }
#endif
}
#endif

#if (MOTOR_A_ENC_LINE >= 5 && MOTOR_A_ENC_LINE <= 9) || (MOTOR_B_ENC_LINE >= 5 && MOTOR_B_ENC_LINE <= 9)
void EXTI9_5_IRQHandler(void)
{
#if MOTOR_A_ENC_LINE >= 5 && MOTOR_A_ENC_LINE <= 9
    if (EXTI->PR & (1 << MOTOR_A_ENC_LINE))
    {
        if (gpio_get(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN))
            Encoder_count1++;
        else
            Encoder_count1--;
        EXTI->PR = 1 << MOTOR_A_ENC_LINE;
    }
#endif
#if MOTOR_B_ENC_LINE >= 5 && MOTOR_B_ENC_LINE <= 9
    if (EXTI->PR & (1 << MOTOR_B_ENC_LINE))
    {
        if (gpio_get(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN))
            Encoder_count2++;
        else
            Encoder_count2--;
        EXTI->PR = 1 << MOTOR_B_ENC_LINE;
    }
#endif
}
#endif

#if (MOTOR_A_ENC_LINE >= 10 && MOTOR_A_ENC_LINE <= 15) || (MOTOR_B_ENC_LINE >= 10 && MOTOR_B_ENC_LINE <= 15)
void EXTI15_10_IRQHandler(void)
{
#if MOTOR_A_ENC_LINE >= 10 && MOTOR_A_ENC_LINE <= 15
    if (EXTI->PR & (1 << MOTOR_A_ENC_LINE))
    {
        if (gpio_get(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN))
            Encoder_count1++;
        else
            Encoder_count1--;
        EXTI->PR = 1 << MOTOR_A_ENC_LINE;
    }
#endif
#if MOTOR_B_ENC_LINE >= 10 && MOTOR_B_ENC_LINE <= 15
    if (EXTI->PR & (1 << MOTOR_B_ENC_LINE))
    {
        if (gpio_get(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN))
            Encoder_count2++;
        else
            Encoder_count2--;
        EXTI->PR = 1 << MOTOR_B_ENC_LINE;
    }
#endif
}
#endif
