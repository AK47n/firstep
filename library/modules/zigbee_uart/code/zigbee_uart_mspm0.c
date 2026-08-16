#include "zigbee_uart_mspm0.h"
#include "config_mspm0.h"

// ============================================================
//  全局变量
// ============================================================
volatile uint8_t  g_key_id           = 0;
volatile uint8_t  g_key_id_updated   = 0;
volatile uint32_t g_key_id_last_tick = 0;
volatile uint32_t g_zigbee_byte_count = 0;  // 诊断：ZIGBEE_UART 收到的总字节数

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
//  UART 初始化：SYSCFG_DL_init() 已配好 ZIGBEE_UART（UART3,
//  PA26/PA25, 115200, RX 中断），这里只开 NVIC 并复位状态机。
// ============================================================
void zigbee_uart_init(void)
{
    NVIC_ClearPendingIRQ(ZIGBEE_UART_INST_INT_IRQN);
    NVIC_EnableIRQ(ZIGBEE_UART_INST_INT_IRQN);
    rx_state = 0;
}

// ============================================================
//  UART 接收中断处理 — 字节级状态机
// ============================================================
void zigbee_rx_handler(void)
{
    uint8_t byte;

    switch (DL_UART_getPendingInterrupt(ZIGBEE_UART_INST))
    {
    case DL_UART_IIDX_RX:
        byte = DL_UART_receiveData(ZIGBEE_UART_INST);
        break;
    default:
        return;
    }

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
                    // mspm0 无全局 g_systick：last_tick 记字节序号（毫秒超时
                    // 请同选 ntb_time 用 get_time_stamp_ms）
                    g_key_id_last_tick = g_zigbee_byte_count;
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

// ZIGBEE_UART_INST_IRQHandler = UART3_IRQHandler（母版 SysConfig 宏）
void ZIGBEE_UART_INST_IRQHandler(void)
{
    zigbee_rx_handler();
}
