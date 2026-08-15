#ifndef _ml_led_h_
#define _ml_led_h_

#include "ml_gpio.h"
#include "pin_config.h"

// 引脚派生自接线单源 pin_config.h（PC13=红 / PC14=黄 / PC15=绿 板载 LED，
// 低电平点亮）——旧定义写死 PA11/PA12 = 蓝药丸 USB DM/DP，灯永不亮
#define LED_GPIO         LED_PORT
#define LED_RED_Pin      LED_RED_PIN
#define LED_YELLOW_Pin   LED_YELLOW_PIN
#define LED_GREEN_Pin    LED_GREEN_PIN

// 便捷控制宏（板载 LED 灌电流：0=点亮，1=熄灭）
#define LED_RED_ON()     gpio_set(LED_GPIO, LED_RED_Pin, 0)
#define LED_RED_OFF()    gpio_set(LED_GPIO, LED_RED_Pin, 1)
#define LED_GREEN_ON()   gpio_set(LED_GPIO, LED_GREEN_Pin, 0)
#define LED_GREEN_OFF()  gpio_set(LED_GPIO, LED_GREEN_Pin, 1)

void led_init(void);

#endif
