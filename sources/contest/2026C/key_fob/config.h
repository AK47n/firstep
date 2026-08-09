#ifndef _key_fob_config_h_
#define _key_fob_config_h_

#include "stdint.h"

// ============================================================
//  数字钥匙端（信标端）引脚映射 + 参数
//  MCU: STM32F103C8T6
// ============================================================

// Zigbee DL-20 无线串口：UART1 (PA9=TX → DL-20 RX, PA10=RX ← DL-20 TX)
#define ZIGBEE_UART         UART_1
#define ZIGBEE_BAUD         115200

// DIP-4 拨码开关 (4位二进制ID，上拉输入，拨到ON=低电平)
#define DIP_GPIO            GPIO_A
#define DIP_PIN0            Pin_0
#define DIP_PIN1            Pin_1
#define DIP_PIN2            Pin_2
#define DIP_PIN3            Pin_3

// 状态指示灯 (PC13 — BluePill 板载LED，低电平点亮)
#define LED_GPIO            GPIO_C
#define LED_PIN             Pin_13

// Zigbee ID 发送间隔 (ms)
#define ZIGBEE_SEND_MS      100

// Zigbee 数据包格式
#define ZIGBEE_SYNC1        0xAA    // 同步头1
#define ZIGBEE_SYNC2        0x55    // 同步头2

#endif
