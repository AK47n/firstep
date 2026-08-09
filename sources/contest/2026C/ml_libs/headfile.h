#ifndef _headfile_h_
#define _headfile_h_

#include "stm32f10x.h"
#include "stdint.h"
#include "stdio.h"
#include "string.h"
#include "math.h"

// 驱动库
#include "ml_uart.h"
#include "ml_tim.h"
#include "ml_oled.h"
#include "ml_delay.h"
#include "ml_gpio.h"
#include "ml_nvic.h"

// 注意：应用模块头文件不再在这里汇总！
//  门锁端: user/main.c, user/isr.c 自行 include (config/filter/uwb_uart/zone/
//          lock_control/debug_uart/zigbee_uart)
//  钥匙端: key_fob/headfile.h 自行 include (config/zigbee_uart)
//  这样 ml_libs 驱动库可以同时被两端工程共用，不会互相污染

// 全局毫秒计数器 (TIM2 1ms中断自增)
extern volatile uint32_t g_systick;

#endif
