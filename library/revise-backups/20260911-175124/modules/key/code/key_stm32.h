#ifndef KEY_STM32_H
#define KEY_STM32_H

#include <stdint.h>

#include "key_instances.h" // 通道宏 + 每通道 (port, pin) 表（默认在工程根，接线单源）

/* 按键读取（stm32，纯驱动，ADR 0009）：上拉输入，低电平 = 按下。
 * 通道表见 key_instances.h：KEY_CHANNEL_COUNT + KEY_PIN_TABLE
 * （单实例默认 1 通道，引脚 KEY_GPIO/KEY_PIN——pin_config.h 单源）。
 * channel 越界钳回首通道。 */

uint8_t get_key_state(uint8_t channel);
void key_init(void);

#endif // KEY_STM32_H
