#ifndef _ml_led_h_
#define _ml_led_h_

#include "ml_gpio.h"
#include "pin_config.h"
#include <stdint.h>

// 引脚派生自接线单源 pin_config.h（PC13=红 / PC14=黄 / PC15=绿 板载 LED）——
// 旧定义写死 PA11/PA12 = 蓝药丸 USB DM/DP，灯永不亮
#define LED_GPIO         LED_PORT
#define LED_RED_Pin      LED_RED_PIN
#define LED_YELLOW_Pin   LED_YELLOW_PIN
#define LED_GREEN_Pin    LED_GREEN_PIN

// 通道编号（与 led 模块 mspm0 侧一致，两平台写法统一）
#define LED_RED          0
#define LED_YELLOW       1
#define LED_GREEN        2

// 便捷控制宏（LED 一脚接地、另一脚接 MCU 引脚：拉电流接法，1=点亮，0=熄灭）
#define LED_RED_ON()     gpio_set(LED_GPIO, LED_RED_Pin, 1)
#define LED_RED_OFF()    gpio_set(LED_GPIO, LED_RED_Pin, 0)
#define LED_GREEN_ON()   gpio_set(LED_GPIO, LED_GREEN_Pin, 1)
#define LED_GREEN_OFF()  gpio_set(LED_GPIO, LED_GREEN_Pin, 0)

void led_init(uint8_t channel);
void led_on(uint8_t channel);
void led_off(uint8_t channel);
void led_toggle(uint8_t channel);

#endif
