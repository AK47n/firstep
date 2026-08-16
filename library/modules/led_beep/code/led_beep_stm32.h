#ifndef LED_BEEP_STM32_H
#define LED_BEEP_STM32_H

#include <stdint.h>

/* 组合模块（stm32）：LED + 蜂鸣器同时控制（依赖 led / beep）。 */

void led_beep_init(void);
void led_beep_on(void);
void led_beep_off(void);

/* 声光报警：灯闪 + 蜂鸣 N 次（on_ms 响/亮，off_ms 停/灭，阻塞式） */
void led_beep_alarm(uint16_t times, uint16_t on_ms, uint16_t off_ms);

#endif // LED_BEEP_STM32_H
