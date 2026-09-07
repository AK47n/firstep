/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《L298N电机驱动模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/l298n-motor-drive-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "l298n_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* L298N 大电流电机驱动（stm32 纯驱动切片，ADR 0009）：
 *   - 方向 + 调速：l298n_set_direction + l298n_set_duty
 *     （页面 AO_Control 原样：dir=1 → IN1=0/IN2=duty、dir=0 → IN1=duty/IN2=0）
 *   - 页面 L298N_Init(pre=72,per=1000)（1kHz 双通道 PWM）换算 ml_pwm：
 *     pwm_init(TIM_3, CH1, FREQ) + pwm_init(TIM_3, CH2, FREQ)——本件按
 *     mspm0 定稿 L298N_PWM_PERIOD 2000u（2000 步骤）取 FREQ=500Hz，
 *     duty 限幅 L298N_PWM_PERIOD-1（页面「speed 范围 0~per-1」语义）
 * 单路（A 端口 IN1/IN2）——页面仅实现 A 端口，B 端口同构扩展留后续；
 * 页面无 EN 代码（跳线帽态——范围外，跳线帽接 VCC 使能）。 */

static uint32_t l298n_duty = 0; /* 当前转速（页面 AO_Control speed 语义，0~per-1） */
static uint8_t l298n_dir = 1;   /* 当前方向（页面 dir 语义：1 正转 / 0 反转） */

/* 页面 0~per-1 占空比刻度 → ml_pwm 的 0~MAX_DUTY(50000) 归一化刻度：
 * pwm_update 按 duty/MAX_DUTY×(ARR+1) 写 CCR（motor/servo 先例换算）——
 * 直传会把 0~1999 当 0~50000 用、满值仅 ~4%：占空比刻度错位修正
 * （code-review 2026-09-08 规格轴发现，首轮直传已修正）。 */
static uint16_t l298n_pwm_duty(uint32_t duty)
{
    return (uint16_t)((uint32_t)duty * (uint32_t)MAX_DUTY
                      / (uint32_t)L298N_PWM_PERIOD);
}

static void l298n_apply(void)
{
    if (l298n_dir == 1) {
        /* 页面 AO_Control(dir=1)：AO1（IN1）= 0、AO2（IN2）= speed */
        pwm_update(L298N_IN1_TIM, L298N_IN1_CH, 0);
        pwm_update(L298N_IN2_TIM, L298N_IN2_CH, l298n_pwm_duty(l298n_duty));
    } else {
        /* 页面 AO_Control(dir=0)：AO1（IN1）= speed、AO2（IN2）= 0 */
        pwm_update(L298N_IN1_TIM, L298N_IN1_CH, l298n_pwm_duty(l298n_duty));
        pwm_update(L298N_IN2_TIM, L298N_IN2_CH, 0);
    }
}

void l298n_init(void)
{
    pwm_init(L298N_IN1_TIM, L298N_IN1_CH, L298N_PWM_FREQ);
    pwm_init(L298N_IN2_TIM, L298N_IN2_CH, L298N_PWM_FREQ);

    l298n_duty = 0;
    l298n_dir = 1;
    l298n_apply();
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
