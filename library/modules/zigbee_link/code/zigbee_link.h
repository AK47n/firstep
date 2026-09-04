#ifndef _zigbee_link_h_
#define _zigbee_link_h_

#include "headfile.h"

// ============================================================
//  通用 Zigbee DL-20 串口透传链路（stm32 版）
//
//  帧格式 (长度前缀 + 校验和):
//    Byte 0: 0xAA  同步头1
//    Byte 1: 0x55  同步头2
//    Byte 2: LEN   负载长度 (1..ZIGBEE_LINK_MAX_PAYLOAD)
//    Byte 3..: PAYLOAD[LEN]
//    末字节: SUM = (0xAA + 0x55 + LEN + ΣPAYLOAD) & 0xFF
//
//  接线：ZIGBEE_UART = USART3，PB10(TX) / PB11(RX)，115200（pin_config.h）。
//  中断：接收经母版 isr.c 的 USART3_IRQHandler → USART3_IRQ_CALLS →
//        zigbee_rx_handler（本模块定义；勿在 main.c 定义 USARTx_IRQHandler）。
//  与 zigbee_uart（固定 DIP-4 ID 帧）/ zigbee_uart_key 共享同一 ZIGBEE_UART；
//  与 zigbee_uart 互斥（同路 RX 只有一个消费者，由互斥组/生成门禁拦截）。
//  协议约定：本帧格式是 zigbee_link 私有约定，与库内固定 DIP-4 ID 帧协议
//  互不兼容——双端必须同为 zigbee_link（混用两侧会静默不通）。
// ============================================================

// 帧格式
#define ZIGBEE_LINK_SYNC1        0xAA
#define ZIGBEE_LINK_SYNC2        0x55
#define ZIGBEE_LINK_MAX_PAYLOAD  32
#define ZIGBEE_LINK_QUEUE_DEPTH  4

// 全局变量
extern volatile uint32_t g_zigbee_link_frame_count; // 累计收到的有效帧数
extern volatile uint32_t g_zigbee_link_byte_count;  // 诊断：USART3 收到的总字节数

// 函数
void zigbee_link_init(void);                       // 复位状态机 + 引脚（含 RX 中断）
void zigbee_link_send(const uint8_t *payload, uint8_t len); // 阻塞发送一帧（1..32 字节）
uint8_t zigbee_link_recv(uint8_t *out, uint8_t max_len);    // 非阻塞取一帧，返回帧长，0=无
uint8_t zigbee_link_available(void);               // 接收队列中完整帧数
void zigbee_rx_handler(void);                      // 由母版 USART3_IRQ_CALLS 调用

#endif
