#include "headfile.h"
#include "zigbee_uart.h"
#include "config.h"

// ============================================================
//  全局变量
// ============================================================
volatile uint8_t  g_key_id           = 0;
volatile uint8_t  g_key_id_updated   = 0;
volatile uint32_t g_key_id_last_tick = 0;
volatile uint32_t g_zigbee_byte_count = 0;  // 诊断：USART3 收到的总字节数

// ============================================================
//  接收状态机 (4字节帧)
//
//  帧格式: [0xAA] [0x55] [ID] [SUM]
//  校验: SUM = (0xAA + 0x55 + ID) & 0xFF
//
//  状态 0: 等待 0xAA
//  状态 1: 等待 0x55 (收到 0xAA 则保持在状态1，其他重同步)
//  状态 2: 读取 ID
//  状态 3: 读取 SUM 并校验
// ============================================================
static volatile uint8_t rx_state = 0;
static volatile uint8_t rx_id    = 0;

// ============================================================
//  USART3 初始化 (PB10=TX, PB11=RX, 115200bps)
// ============================================================
void zigbee_uart_init(void)
{
    uart_init(ZIGBEE_UART, ZIGBEE_BAUD, 0x01);  // priority=0x01 开启接收中断
    rx_state = 0;
}

// ============================================================
//  USART3 中断处理 — 字节级状态机
//  由 USART3_IRQHandler 调用
// ============================================================
void zigbee_rx_handler(void)
{
    uint8_t byte = (uint8_t)(ZIGBEE_UART_INST->DR & 0xFF);  // ZIGBEE_UART_INST = USART3（pin_config.h）
    g_zigbee_byte_count++;  // 每收到1字节+1

    switch (rx_state)
    {
        case 0:
            // 等待同步头1: 0xAA
            if (byte == ZIGBEE_SYNC1)
                rx_state = 1;
            // 否则丢弃，保持状态0
            break;

        case 1:
            // 等待同步头2: 0x55
            if (byte == ZIGBEE_SYNC2)
            {
                rx_state = 2;
            }
            else if (byte == ZIGBEE_SYNC1)
            {
                // 又是 0xAA，保持在状态1 (重新等 0x55)
                // rx_state 保持 1
            }
            else
            {
                // 干扰字节，回状态0
                rx_state = 0;
            }
            break;

        case 2:
            // 读取 ID (只取低4位)
            rx_id    = byte & 0x0F;
            rx_state = 3;
            break;

        case 3:
            // 读取 SUM 并校验
            {
                uint8_t sum_calc = (uint8_t)(ZIGBEE_SYNC1 + ZIGBEE_SYNC2 + rx_id);
                if (byte == sum_calc)
                {
                    // 校验通过 → 更新标签ID
                    g_key_id           = rx_id;
                    g_key_id_updated   = 1;
                    g_key_id_last_tick = g_systick;
                }
                // 校验失败则静默丢弃
            }
            rx_state = 0;
            break;

        default:
            rx_state = 0;
            break;
    }
}
