#ifndef KEY_H
#define KEY_H

#include "ti_msp_dl_config.h"
#include <stdint.h>

/* 启动按键读取：上拉输入，低电平 = 按下（返回 1）。 */
uint8_t get_key_state(void);

#endif
