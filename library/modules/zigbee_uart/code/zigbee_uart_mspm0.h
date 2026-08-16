#ifndef _zigbee_uart_mspm0_h_
#define _zigbee_uart_mspm0_h_

#include "ti_msp_dl_config.h"
#include <stdint.h>

// ============================================================
//  接收端 Zigbee DL-20 通信模块（mspm0 版）
//
//  数据包格式 (4字节，每 100ms 一帧):
//    Byte 0: 0xAA  同步头1
//    Byte 1: 0x55  同步头2
//    Byte 2: ID    发射端 DIP-4 值 (0x00~0x0F, ON=1)
//    Byte 3: SUM   (0xAA + 0x55 + ID) & 0xFF
//
//  接线：ZIGBEE_UART = UART3，PA26(TX) / PA25(RX)，115200 8N1（SysConfig）。
//  中断：ZIGBEE_UART_INST_IRQHandler 在本模块 .c 内定义，main.c 无需再定义；
//        与 zigbee_uart_key 共享同一 SysConfig 实例（key 侧不开 NVIC）。
// ============================================================

// 帧格式
#define ZIGBEE_SYNC1        0xAA
#define ZIGBEE_SYNC2        0x55
#define ZIGBEE_FRAME_SIZE   4

// 全局变量
extern volatile uint8_t  g_key_id;           // 最新收到的标签ID (0-15)
extern volatile uint8_t  g_key_id_updated;   // 收到有效帧时置1，主循环消费后清0
extern volatile uint32_t g_key_id_last_tick; // mspm0 记字节序号（无全局 systick；
                                             // 毫秒超时请同选 ntb_time 用
                                             // get_time_stamp_ms）
extern volatile uint32_t g_zigbee_byte_count; // 诊断：ZIGBEE_UART 收到的总字节数

// 函数
void zigbee_uart_init(void);   // SYSCFG_DL_init() 后调用：开 ZIGBEE_UART NVIC
void zigbee_rx_handler(void);  // 由 ZIGBEE_UART_INST_IRQHandler 调用

#endif
