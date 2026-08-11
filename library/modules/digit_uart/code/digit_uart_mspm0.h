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

#endif
