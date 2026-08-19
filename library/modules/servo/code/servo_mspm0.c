#include "servo.h"
#include "ti_msp_dl_config.h"

/* 舵机（mspm0，PWM 底座）：周期与脉宽按 SERVO_PWM_INST_CLK_FREQ 运行时
 * 计算（照 step_motor 先例，不依赖母版 ULPCLK 假设）：
 *   周期 = INST_CLK_FREQ / 50（20ms）
 *   0° 脉宽 = 0.5ms = 周期 / 40；全行程 2ms / 180° = 周期 / 1800 每度 */

static uint32_t servo_period(void)
{
    return SERVO_PWM_INST_CLK_FREQ / 50;
}

static uint32_t servo_duty_for_angle(uint16_t angle)
{
    uint32_t period = servo_period();
    return period / 40 + (uint32_t)angle * period / 1800;
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
    if (angle > 180) {
        angle = 180;
    }
    DL_Timer_setCaptureCompareValue(
        SERVO_PWM_INST, servo_duty_for_angle(angle), GPIO_SERVO_PWM_C0_IDX);
}
