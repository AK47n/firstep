#ifndef KEY_STM32_H
#define KEY_STM32_H

#include <stdint.h>

/* 按键读取（stm32）：上拉输入，低电平 = 按下（返回 1）。 */
uint8_t get_key_state(void);

#endif // KEY_STM32_H
