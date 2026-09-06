#include "l298n.h"

/* L298N 大电流电机驱动（mspm0 纯驱动切片，ADR 0009）：
 *   - 方向 + 调速：l298n_set_direction + l298n_set_duty
 *     （页面 AO_Control 原样：dir=1 → C0=0/C1=duty、dir=0 → C0=duty/C1=0）
 *   - 使能：l298n_init 置高 EN（页面「5V 使能高电平有效」）
 * 单路（A 端口 IN1/IN2）——页面仅实现 A 端口，B 端口同构扩展留后续。
 * 页面 DL_TimerG_setCaptureCompareValue 按 motor.c 先例用
 * DL_Timer_setCaptureCompareValue（SDK 2.11 同义 API）。 */

static uint32_t l298n_duty = 0; /* 当前转速（页面 AO_Control speed 语义） */
static uint8_t l298n_dir = 1;   /* 当前方向（页面 dir 语义：1 正转 / 0 反转） */

static void l298n_apply(void)
{
    if (l298n_dir == 1) {
        /* 页面 AO_Control(dir=1)：AO1（C0）= 0、AO2（C1）= speed */
        DL_Timer_setCaptureCompareValue(L298N_PWM_INST, 0,
                                        GPIO_L298N_PWM_C0_IDX);
        DL_Timer_setCaptureCompareValue(L298N_PWM_INST, l298n_duty,
                                        GPIO_L298N_PWM_C1_IDX);
    } else {
        /* 页面 AO_Control(dir=0)：AO1（C0）= speed、AO2（C1）= 0 */
        DL_Timer_setCaptureCompareValue(L298N_PWM_INST, l298n_duty,
                                        GPIO_L298N_PWM_C0_IDX);
        DL_Timer_setCaptureCompareValue(L298N_PWM_INST, 0,
                                        GPIO_L298N_PWM_C1_IDX);
    }
}

void l298n_init(void)
{
    /* 使能端高有效（页面「5V 使能...高电平有效，常态跳线帽接 VCC；
     * PWM 调速时取下跳线帽」——取帽后由 GPIO 置高） */
    DL_GPIO_setPins(L298N_PORT, L298N_EN_PIN);

    l298n_duty = 0;
    l298n_dir = 1;
    l298n_apply();
    DL_Timer_startCounter(L298N_PWM_INST);
}

void l298n_set_duty(uint32_t duty)
{
    uint32_t max_duty = L298N_PWM_PERIOD - 1u;

    if (duty > max_duty) {
        duty = max_duty;
    }
    l298n_duty = duty;
    l298n_apply();
}

void l298n_set_direction(uint8_t dir)
{
    l298n_dir = (dir == 1) ? 1u : 0u;
    l298n_apply();
}
