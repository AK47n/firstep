#ifndef _debug_uart_mspm0_h_
#define _debug_uart_mspm0_h_

#include "ti_msp_dl_config.h"
#include <stdint.h>
#include <stdio.h>

// ============================================================
//  调试串口（mspm0 版）：DEBUG_UART = UART2，PA23(TX)/PA22(RX)，
//  115200 8N1（SysConfig）。与 stm32 版同名同形：
//  debug_uart_init / debug_uart_send / debug_uart_rx_handler /
//  debug_cmd_poll + DEBUG_PRINTF。
//
//  中断：DEBUG_UART_INST_IRQHandler 在模块 .c 内定义，main.c
//  无需再定义。debug_cmd_poll 在 mspm0 只回显收到的命令——
//  LED/蜂鸣器指令执行请用 led / beep 模块（调试模块不拖依赖）。
// ============================================================

// 调试开关 (0=关闭调试输出, 1=开启)
#define DEBUG_UART_ENABLE   1

void debug_uart_init(void);       // SYSCFG_DL_init() 后调用：开 DEBUG_UART NVIC
void debug_uart_send(const char *str);  // 阻塞发送字符串
void debug_uart_rx_handler(void);       // 由 DEBUG_UART_INST_IRQHandler 调用
void debug_cmd_poll(void);              // 主循环调用：回显已收命令

#if DEBUG_UART_ENABLE
    #define DEBUG_PRINTF(fmt, ...)  \
        do { \
            char _dbg_buf[128]; \
            snprintf(_dbg_buf, sizeof(_dbg_buf), fmt, ##__VA_ARGS__); \
            debug_uart_send(_dbg_buf); \
        } while(0)
#else
    #define DEBUG_PRINTF(fmt, ...)  ((void)0)
#endif

#endif
