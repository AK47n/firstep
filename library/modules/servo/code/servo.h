/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《SG90舵机》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/sg90-steering-engine.html
 * （批 11 C 类核对：本件 = 语义同源页面——50Hz/0.5-2.5ms/0-180° 逐项吻合；
 * 16 路舵机 PCA9685 页对应库内 pca9685 模块——见 manifest notes）；
 * 使用 / 复制 / 修改 / 传播请遵循立创版权要求。
 */
#ifndef SERVO_H
#define SERVO_H

#include <stdint.h>

/* 舵机角度控制（双平台对偶 API，b1-adc-servo/02）：
 *   servo_init(servo_id, channel)     初始化（50Hz/20ms 周期，舵机归 0°）
 *   servo_set_angle(servo_id, angle)  角度 0-180（越界钳位到端点）
 * 引脚由生成器绑定（stm32 pin_config.h 宏 / mspm0 syscfg ccp0Pin），
 * 模块代码不吃引脚字面量。 */

void servo_init(uint8_t servo_id, uint8_t channel);
void servo_set_angle(uint8_t servo_id, uint16_t angle);

#endif
