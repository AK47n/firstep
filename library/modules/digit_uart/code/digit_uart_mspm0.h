#ifndef _digit_uart_mspm0_h_
#define _digit_uart_mspm0_h_
#include "ti_msp_dl_config.h"
#include <stdint.h>

#define MAX_DIGITS 4   // 一帧最多识别几个数字

typedef struct {
    char label[8];        // 数字标签
    float confidence;     // 置信度
    int cx, cy;           // 中心坐标
} DigitInfo;

typedef struct {
    DigitInfo digits[MAX_DIGITS];
    uint8_t count;        // 本帧识别到的数字个数
    uint8_t updated;      // 是否有新数据
} DigitResult;

extern DigitResult digit_result;
extern volatile uint32_t rx_byte_count;
extern volatile uint32_t rx_overflow;
extern volatile uint32_t rx_error;

void digit_uart_init(void);
void digit_uart_flush(void);
void digit_uart_rx_handler(void);
void digit_uart_parse(void);


/* 中断挂载：DIGIT_UART（UART1）与 ball_detect 共享同一实例。两模块同选时，
 * main.c 只定义一个 DIGIT_UART_INST_IRQHandler（= UART1_IRQHandler），并在
 * 其中依次调用 digit_uart_rx_handler() 与 ball_detect_rx_handler()。
 * 只选本模块时 handler 里只调 digit_uart_rx_handler()。 */
#endif
