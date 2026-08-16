#ifndef LED_H
#define LED_H

#include <stdint.h>

// 通道编号（地猛星只有一个用户 LED，统一用 LED_RED；多灯时再扩）
#define LED_RED    0
#define LED_YELLOW 0
#define LED_GREEN  0

void led_init(uint8_t channel);
void led_on(uint8_t channel);
void led_off(uint8_t channel);
void led_toggle(uint8_t channel);

#endif // LED_H
