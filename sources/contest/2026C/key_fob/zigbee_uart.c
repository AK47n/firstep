#include "headfile.h"
#include "zigbee_uart.h"
#include "config.h"

// ============================================================
//  Zigbee DL-20 初始化 (UART1, 115200bps)
// ============================================================
void zigbee_uart_init(void)
{
    uart_init(ZIGBEE_UART, ZIGBEE_BAUD, 0x00);  // 只发不收，不开接收中断
}

// ============================================================
//  发送钥匙ID — 4字节帧
//    [0xAA] [0x55] [ID] [SUM]
//    SUM = (0xAA + 0x55 + ID) & 0xFF
// ============================================================
void zigbee_send_id(uint8_t key_id)
{
    uint8_t id = key_id & 0x0F;  // 只取低4位
    uint8_t sum = (uint8_t)(0xAA + 0x55 + id);

    uart_sendbyte(ZIGBEE_UART, 0xAA);
    uart_sendbyte(ZIGBEE_UART, 0x55);
    uart_sendbyte(ZIGBEE_UART, id);
    uart_sendbyte(ZIGBEE_UART, sum);
}
