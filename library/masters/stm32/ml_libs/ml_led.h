#ifndef _ml_led_h_
#define _ml_led_h_

#include "ml_gpio.h"
#include "pin_config.h"
#include "led_instances.h" // 通道宏 + 每通道 (port, pin) 表（生成器多实例渲染产物）
#include <stdint.h>

// LED 驱动（内嵌母版，led 模块 stm32 侧空条目 = 本实现）。通道表见
// led_instances.h：LED_CHANNEL_COUNT + LED_PIN_TABLE（单实例默认三通道
// PC13/14/15，引脚取 pin_config.h——接线单源）。极性已封装：LED 一脚接地、
// 另一脚接 MCU 引脚（拉电流接法），led_on = 亮。

void led_init(uint8_t channel);
void led_on(uint8_t channel);
void led_off(uint8_t channel);
void led_toggle(uint8_t channel);

#endif
