#ifndef LED_H
#define LED_H

#include <stdint.h>

#include "led_instances.h" // 通道宏 + 每通道 (port, pin) 表（生成器多实例渲染产物）

// LED 驱动（地猛星）。通道表见 led_instances.h：LED_CHANNEL_COUNT +
// LED_PIN_TABLE（单实例默认 1 通道 PA15，LED_BEEP 组）。极性已封装：
// LED 一脚接地、另一脚接 MCU 引脚（拉电流接法），led_on = 亮。

void led_init(uint8_t channel);
void led_on(uint8_t channel);
void led_off(uint8_t channel);
void led_toggle(uint8_t channel);

#endif // LED_H
