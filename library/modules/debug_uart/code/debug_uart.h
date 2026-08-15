#ifndef _debug_uart_h_
#define _debug_uart_h_

#include "headfile.h"
#include <stdio.h>  // sprintf（DEBUG_PRINTF 宏用；缺声明 = 隐式声明 6 警，板级引脚配置迁移验收发现）

// ============================================================
//  调试串口 (UART2: PA2=TX, PA3=RX)
//  用于打印原始UWB帧数据、系统状态等调试信息
//
//  使用方法：
//    debug_uart_init();
//    debug_printf("distance=%lu azimuth=%d\r\n", dist, az);
// ============================================================

// 调试开关 (0=关闭调试输出, 1=开启)
#define DEBUG_UART_ENABLE   1

void debug_uart_init(void);
void debug_uart_send(const char *str);

// 调试命令 (UART2 RX)
void debug_uart_rx_handler(void);   // 由母版 isr.c 的 USART2_IRQHandler 经
                                 // USART2_IRQ_CALLS 聚合宏调用（勿在
                                 // main.c 定义 USARTx_IRQHandler）
void debug_cmd_poll(void);          // 主循环调用

#if DEBUG_UART_ENABLE
    #define DEBUG_PRINTF(fmt, ...)  \
        do { \
            char _dbg_buf[128]; \
            sprintf(_dbg_buf, fmt, ##__VA_ARGS__); \
            debug_uart_send(_dbg_buf); \
        } while(0)
#else
    #define DEBUG_PRINTF(fmt, ...)  ((void)0)
#endif

#endif
