#ifndef _zigbee_link_mspm0_h_
#define _zigbee_link_mspm0_h_

#include "ti_msp_dl_config.h"
#include <stdint.h>

// ============================================================
//  通用 Zigbee DL-20 串口透传链路（mspm0 版）
//
//  帧格式 (长度前缀 + 校验和):
//    Byte 0: 0xAA  同步头1
//    Byte 1: 0x55  同步头2
//    Byte 2: LEN   负载长度 (1..ZIGBEE_LINK_MAX_PAYLOAD)
//    Byte 3..: PAYLOAD[LEN]
//    末字节: SUM = (0xAA + 0x55 + LEN + ΣPAYLOAD) & 0xFF
//
//  接线：ZIGBEE_UART = UART3，PA26(TX) / PA25(RX)，115200 8N1（SysConfig）。
//  中断：ZIGBEE_UART_INST_IRQHandler 在本模块 .c 内定义，main.c 无需再定义；
//        与 zigbee_uart / zigbee_uart_key 共享同一 SysConfig 实例（互斥组拦截
//        与 zigbee_uart 同选——同路 RX 只有一个消费者）。
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
extern volatile uint32_t g_zigbee_link_byte_count;  // 诊断：ZIGBEE_UART 收到的总字节数

// 函数
void zigbee_link_init(void);                       // SYSCFG_DL_init() 后调用：开 ZIGBEE_UART NVIC
void zigbee_link_send(const uint8_t *payload, uint8_t len); // 阻塞发送一帧（1..32 字节）
uint8_t zigbee_link_recv(uint8_t *out, uint8_t max_len);    // 非阻塞取一帧，返回帧长，0=无
uint8_t zigbee_link_available(void);               // 接收队列中完整帧数
void zigbee_rx_handler(void);                      // 由 ZIGBEE_UART_INST_IRQHandler 调用

#endif
