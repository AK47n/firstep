#ifndef _ml_led_h_
#define _ml_led_h_

#include "ml_gpio.h"

// 引脚定义：PA11=红灯，PA12=绿灯
#define LED_GPIO         GPIO_A
#define LED_RED_Pin      Pin_11
#define LED_GREEN_Pin    Pin_12

// 便捷控制宏（高电平驱动：1=点亮，0=熄灭）
#define LED_RED_ON()     gpio_set(LED_GPIO, LED_RED_Pin, 1)
#define LED_RED_OFF()    gpio_set(LED_GPIO, LED_RED_Pin, 0)
#define LED_GREEN_ON()   gpio_set(LED_GPIO, LED_GREEN_Pin, 1)
#define LED_GREEN_OFF()  gpio_set(LED_GPIO, LED_GREEN_Pin, 0)

void led_init(void);

#endif
