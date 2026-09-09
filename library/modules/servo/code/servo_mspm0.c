#include "servo.h"
#include "ti_msp_dl_config.h"

/* 舵机（mspm0，PWM 底座）：周期与脉宽按 SERVO_PWM_INST_CLK_FREQ 运行时
 * 计算（照 step_motor 先例，不依赖母版 ULPCLK 假设）：
 *   周期 = 1s / SERVO_FREQ_HZ 的计数值
 *   脉宽 = 角度换算（servo.h 的 SERVO_PULSE_US 单源）→ 按周期比例折算 */

static uint32_t servo_period(void)
{
    return SERVO_PWM_INST_CLK_FREQ / SERVO_FREQ_HZ;
}

static uint32_t servo_duty_for_angle(uint16_t angle)
{
    uint32_t period = servo_period();
    /* 64 位中间量：period 最大 ~1.6e6（80MHz/50）× 脉宽 2500us 会溢出 32 位 */
    return (uint32_t)((uint64_t)period * SERVO_PULSE_US(angle) / SERVO_PERIOD_US);
}

void servo_init(uint8_t servo_id, uint8_t channel)
{
    (void)servo_id;
    (void)channel;
    DL_Timer_setLoadValue(SERVO_PWM_INST, servo_period());
    DL_Timer_setCaptureCompareValue(
        SERVO_PWM_INST, servo_duty_for_angle(0), GPIO_SERVO_PWM_C0_IDX);
    DL_Timer_startCounter(SERVO_PWM_INST);
}

void servo_set_angle(uint8_t servo_id, uint16_t angle)
{
    (void)servo_id;
    if (angle > SERVO_ANGLE_MAX) {
        angle = SERVO_ANGLE_MAX;
    }
    DL_Timer_setCaptureCompareValue(
        SERVO_PWM_INST, servo_duty_for_angle(angle), GPIO_SERVO_PWM_C0_IDX);
}
