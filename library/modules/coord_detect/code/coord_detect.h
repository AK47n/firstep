#ifndef _coord_detect_h_
#define _coord_detect_h_
#include "ti_msp_dl_config.h"
#include <stdint.h>

// ==================== 钢珠检测结果 ====================

typedef struct {
    int cx, cy;               // 钢珠中心坐标（图像空间 1280x720）
    float confidence;         // 置信度 0~1
    int x1, y1, x2, y2;      // 边界框
    uint8_t detected;         // 本帧是否检测到钢珠（1=有, 0=无）
    uint8_t updated;          // 是否有新数据（消费后清零）
    uint32_t lost_frames;     // 连续丢失帧数
} CoordResult;

extern CoordResult coord_result;
extern volatile uint32_t coord_rx_byte_count;
extern volatile uint32_t coord_rx_overflow;
extern volatile uint32_t coord_rx_error;

void coord_detect_init(void);
void coord_detect_flush(void);
void coord_detect_rx_handler(void);
void coord_detect_parse(void);

/* 中断挂载：DIGIT_UART（UART1）与 digit_uart 共享同一实例。两模块同选时，
 * main.c 只定义一个 DIGIT_UART_INST_IRQHandler（= UART1_IRQHandler），并在
 * 其中依次调用 digit_uart_rx_handler() 与 coord_detect_rx_handler()。
 * 只选本模块时 handler 里只调 coord_detect_rx_handler()。 */

#endif
