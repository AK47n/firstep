#ifndef _zigbee_uart_key_h_
#define _zigbee_uart_key_h_

#include "headfile.h"

// ============================================================
//  钥匙端 Zigbee DL-20 通信模块
//  功能：将本机 DIP-4 ID 通过 Zigbee 无线发送给门锁端
//
//  数据包格式 (4字节，每 100ms 发送一次):
//    Byte 0: 0xAA  同步头1
//    Byte 1: 0x55  同步头2
//    Byte 2: ID    钥匙端 DIP-4 值 (0x00~0x0F)
//    Byte 3: SUM   (0xAA + 0x55 + ID) & 0xFF
// ============================================================

void zigbee_uart_key_init(void);
void zigbee_uart_key_send_id(uint8_t key_id);

#endif
