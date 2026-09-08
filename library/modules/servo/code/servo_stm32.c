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
 * 0-180°。MAX_DUTY=50000 → 0.5ms=1250、2.5ms=6250，角度线性插值。 */

static uint16_t servo_duty_for_angle(uint16_t angle)
{
    return 1250 + (uint16_t)((uint32_t)angle * 5000 / 180);
}

void servo_init(uint8_t servo_id, uint8_t channel)
{
    (void)servo_id;
    (void)channel;
    pwm_init(SERVO_PWM_TIM, SERVO_PWM_CH, 50);
    pwm_update(SERVO_PWM_TIM, SERVO_PWM_CH, servo_duty_for_angle(0));
}

void servo_set_angle(uint8_t servo_id, uint16_t angle)
{
    (void)servo_id;
    if (angle > 180) {
        angle = 180;
    }
    pwm_update(SERVO_PWM_TIM, SERVO_PWM_CH, servo_duty_for_angle(angle));
}
