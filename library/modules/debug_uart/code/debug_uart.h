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

// 命令台接口（工单 module-hwcheck/06）：把"收到了什么命令"交给应用层。
// 检测程序给每件器件挂了复测字符，它要**先看一眼**再决定认不认领——认领
// （配方命令 / 帮助）才 consume，其余一律不碰，留给上面的 debug_cmd_poll()。
// 分工刻意拆成两个：peek 只读、consume 才清空；合成一个"取走"接口的话，
// 既有 r/y/g/o/b 的语义就落到应用层手里了（那就不是"一个字节不动"）。
const char *debug_cmd_peek(void);   // 收到的命令（没有 = 空串，只读）
void debug_cmd_consume(void);       // 应用层处理完 → 清空命令缓冲

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
