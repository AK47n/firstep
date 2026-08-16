#include "zigbee_uart_key_mspm0.h"
#include "config_mspm0.h"

// ============================================================
//  Zigbee DL-20 初始化（ZIGBEE_UART = UART3, 115200bps, SysConfig
//  已配好；只发不收——不开 NVIC，IRQHandler 归接收侧模块）
// ============================================================
void zigbee_uart_key_init(void)
{
    // 发送侧无中断需求：SYSCFG_DL_init() 已使能 UART，
    // 这里刻意不调 NVIC_EnableIRQ(ZIGBEE_UART_INST_INT_IRQN)。
}

// ============================================================
//  发送标签ID — 4字节帧
//    [0xAA] [0x55] [ID] [SUM]
//    SUM = (0xAA + 0x55 + ID) & 0xFF
// ============================================================
void zigbee_uart_key_send_id(uint8_t key_id)
{
    uint8_t id = key_id & 0x0F;  // 只取低4位
    uint8_t sum = (uint8_t)(0xAA + 0x55 + id);

    DL_UART_transmitDataBlocking(ZIGBEE_UART_INST, 0xAA);
    DL_UART_transmitDataBlocking(ZIGBEE_UART_INST, 0x55);
    DL_UART_transmitDataBlocking(ZIGBEE_UART_INST, id);
    DL_UART_transmitDataBlocking(ZIGBEE_UART_INST, sum);
}
