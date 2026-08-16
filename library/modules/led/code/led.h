#ifndef LED_H
#define LED_H

#include <stdint.h>

// 通道编号（地猛星只有一个用户 LED，统一用 LED_RED；多灯时再扩）
#define LED_RED    0
#define LED_YELLOW 0
#define LED_GREEN  0

// 便捷控制宏（与 stm32 母版 ml_led 对齐，module-polish/05）
#define LED_RED_ON()     led_on(LED_RED)
#define LED_RED_OFF()    led_off(LED_RED)
#define LED_YELLOW_ON()  led_on(LED_YELLOW)
#define LED_YELLOW_OFF() led_off(LED_YELLOW)
#define LED_GREEN_ON()   led_on(LED_GREEN)
#define LED_GREEN_OFF()  led_off(LED_GREEN)

void led_init(uint8_t channel);
void led_on(uint8_t channel);
void led_off(uint8_t channel);
void led_toggle(uint8_t channel);

#endif // LED_H
