/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《SG90舵机》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/sg90-steering-engine.html
 * （批 11 C 类核对：本件 = 语义同源页面——50Hz/0.5-2.5ms/0-180° 逐项吻合；
 * 16 路舵机 PCA9685 页对应库内 pca9685 模块——见 manifest notes）；
 * 使用 / 复制 / 修改 / 传播请遵循立创版权要求。
 */
#include "servo.h"
#include "pin_config.h"
#include "headfile.h"

/* 舵机（stm32，母版 ml_pwm 封装）：50Hz/20ms 周期，0.5-2.5ms 脉宽映射
 * 0-180°。角度换算常量单源 = servo.h（SERVO_* 宏）；本文件只做
 * 「脉宽 → MAX_DUTY 满量程计数值」的比例换算。 */

static uint16_t servo_duty_for_angle(uint16_t angle)
{
    return (uint16_t)((uint32_t)MAX_DUTY * SERVO_PULSE_US(angle) / SERVO_PERIOD_US);
}

void servo_init(uint8_t servo_id, uint8_t channel)
{
    (void)servo_id;
    (void)channel;
    pwm_init(SERVO_PWM_TIM, SERVO_PWM_CH, SERVO_FREQ_HZ);
    pwm_update(SERVO_PWM_TIM, SERVO_PWM_CH, servo_duty_for_angle(0));
}

void servo_set_angle(uint8_t servo_id, uint16_t angle)
{
    (void)servo_id;
    if (angle > SERVO_ANGLE_MAX) {
        angle = SERVO_ANGLE_MAX;
    }
    pwm_update(SERVO_PWM_TIM, SERVO_PWM_CH, servo_duty_for_angle(angle));
}
