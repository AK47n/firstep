#ifndef _key_fob_headfile_h_
#define _key_fob_headfile_h_

#include "stm32f10x.h"
#include "stdint.h"
#include "stdio.h"
#include "string.h"

// 驱动库 (与门锁端共享 ml_libs/)
#include "ml_uart.h"
#include "ml_tim.h"
#include "ml_delay.h"
#include "ml_gpio.h"
#include "ml_nvic.h"

// 钥匙端应用模块
#include "config.h"
#include "zigbee_uart.h"

// 全局毫秒计数器 (TIM2 1ms中断自增)
extern volatile uint32_t g_systick;

#endif
