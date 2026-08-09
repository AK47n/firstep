#ifndef _zigbee_uart_h_
#define _zigbee_uart_h_

#include "headfile.h"

// ============================================================
//  门锁端 Zigbee DL-20 通信模块
//  功能：接收钥匙端通过 Zigbee 发来的 DIP-4 ID
//
//  数据包格式 (4字节，每 100ms 一帧):
//    Byte 0: 0xAA  同步头1
//    Byte 1: 0x55  同步头2
//    Byte 2: ID    钥匙端 DIP-4 值 (0x00~0x0F, ON=1)
//    Byte 3: SUM   (0xAA + 0x55 + ID) & 0xFF
//
//  离场判断: 连续 3~5 帧未收到 (约 500ms)
// ============================================================

// 帧格式
#define ZIGBEE_SYNC1        0xAA
#define ZIGBEE_SYNC2        0x55
#define ZIGBEE_FRAME_SIZE   4

// 全局变量
extern volatile uint8_t  g_key_id;           // 最新收到的钥匙ID (0-15)
extern volatile uint8_t  g_key_id_updated;   // 收到有效帧时置1，主循环消费后清0
extern volatile uint32_t g_key_id_last_tick; // 最后一次收到有效帧的 tick
extern volatile uint32_t g_zigbee_byte_count; // 诊断：USART3 收到的总字节数

// 函数
void zigbee_uart_init(void);
void zigbee_rx_handler(void);   // USART3 ISR 调用

#endif
