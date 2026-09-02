#ifndef __ML_SYSTICK_H
#define __ML_SYSTICK_H

#include "stm32f10x.h"

extern volatile uint32_t g_systick;  // 1ms 系统节拍计数（模块超时/定时逻辑用）

void systick_init(void);             // 配置 SysTick 1ms 中断，使 g_systick 开始递增

#endif
