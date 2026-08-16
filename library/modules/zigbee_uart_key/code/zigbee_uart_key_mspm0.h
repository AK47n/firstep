#ifndef _zigbee_uart_key_mspm0_h_
#define _zigbee_uart_key_mspm0_h_

#include "ti_msp_dl_config.h"
#include <stdint.h>

// ============================================================
//  发射端 Zigbee DL-20 通信模块（mspm0 版）
//
//  数据包格式 (4字节，每 100ms 发送一次):
//    Byte 0: 0xAA  同步头1
//    Byte 1: 0x55  同步头2
//    Byte 2: ID    发射端 DIP-4 值 (0x00~0x0F)
//    Byte 3: SUM   (0xAA + 0x55 + ID) & 0xFF
//
//  接线：与 zigbee_uart 共享 ZIGBEE_UART = UART3，PA26(TX)/PA25(RX)，
//        115200 8N1（SysConfig）。发送侧不开 NVIC、不定义 IRQHandler
//        （接收侧同选时由 zigbee_uart_mspm0.c 定义）。
// ============================================================

void zigbee_uart_key_init(void);             // SYSCFG_DL_init() 后调用（只发不收）
void zigbee_uart_key_send_id(uint8_t key_id); // 发送 DIP-4 ID（低 4 位）

#endif
