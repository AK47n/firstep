#include "headfile.h"
#include "zigbee_link.h"
#include "config.h"

// ============================================================
//  全局变量
// ============================================================
volatile uint32_t g_zigbee_link_frame_count = 0;  // 累计收到的有效帧数
volatile uint32_t g_zigbee_link_byte_count  = 0;  // 诊断：USART3 收到的总字节数

// ============================================================
//  接收状态机（长度前缀帧）
//
//  帧格式: [0xAA] [0x55] [LEN] [PAYLOAD...] [SUM]
//  校验: SUM = (0xAA + 0x55 + LEN + ΣPAYLOAD) & 0xFF
//
//  状态 0: 等待 0xAA
//  状态 1: 等待 0x55 (收到 0xAA 则保持在状态1，其他重同步)
//  状态 2: 读取 LEN
//  状态 3: 读取 PAYLOAD（LEN 字节）
//  状态 4: 读取 SUM 并校验 → 入队
// ============================================================
static volatile uint8_t rx_state = 0;
static volatile uint8_t rx_len   = 0;
static volatile uint8_t rx_index = 0;
static volatile uint8_t rx_buf[ZIGBEE_LINK_MAX_PAYLOAD];

// 帧队列（ISR 写 / 主循环读）
static uint8_t q_buf[ZIGBEE_LINK_QUEUE_DEPTH][ZIGBEE_LINK_MAX_PAYLOAD];
static volatile uint8_t q_len[ZIGBEE_LINK_QUEUE_DEPTH] = {0};
static volatile uint8_t q_head = 0;
static volatile uint8_t q_tail = 0;
static volatile uint8_t q_count = 0;

// ============================================================
//  UART 初始化（引脚/实例 = pin_config.h 宏，115200bps；
//  uart_pin_init_ex 内含 RX 中断使能 + NVIC）
// ============================================================
void zigbee_link_init(void)
{
    uart_pin_init_ex(ZIGBEE_UART, ZIGBEE_UART_TX_GPIO, ZIGBEE_UART_TX_Pin,
                     ZIGBEE_UART_RX_GPIO, ZIGBEE_UART_RX_Pin);
    rx_state = 0;
    rx_index = 0;
    q_head   = 0;
    q_tail   = 0;
    q_count  = 0;
}

// ============================================================
//  发送一帧（阻塞）：[0xAA] [0x55] [LEN] [PAYLOAD...] [SUM]
// ============================================================
void zigbee_link_send(const uint8_t *payload, uint8_t len)
{
    uint8_t i;
    uint8_t sum;

    if (payload == 0 || len == 0 || len > ZIGBEE_LINK_MAX_PAYLOAD)
        return;  // 非法负载：静默丢弃（宁可不发，不发坏帧）

    sum = (uint8_t)(ZIGBEE_LINK_SYNC1 + ZIGBEE_LINK_SYNC2 + len);
    for (i = 0; i < len; i++)
        sum = (uint8_t)(sum + payload[i]);

    uart_sendbyte(ZIGBEE_UART, ZIGBEE_LINK_SYNC1);
    uart_sendbyte(ZIGBEE_UART, ZIGBEE_LINK_SYNC2);
    uart_sendbyte(ZIGBEE_UART, len);
    for (i = 0; i < len; i++)
        uart_sendbyte(ZIGBEE_UART, payload[i]);
    uart_sendbyte(ZIGBEE_UART, sum);
}

// ============================================================
//  接收队列：非阻塞取一帧（返回负载长度，0 = 无帧）
// ============================================================
uint8_t zigbee_link_recv(uint8_t *out, uint8_t max_len)
{
    uint8_t n;
    uint8_t i;

    if (out == 0 || q_count == 0)
        return 0;
    n = q_len[q_head];
    if (max_len < n)
        n = max_len;  // 调用方缓冲区不足：按 max_len 截断取走（剩余载荷丢弃）
    for (i = 0; i < n; i++)
        out[i] = q_buf[q_head][i];
    q_count--;  // 整帧取走（截断也算取走：剩余载荷丢弃，不再可取）
    q_head = (uint8_t)((q_head + 1) % ZIGBEE_LINK_QUEUE_DEPTH);
    return n;
}

uint8_t zigbee_link_available(void)
{
    return q_count;
}

// ============================================================
//  UART 接收中断处理 — 字节级状态机
//  由母版 isr.c 的 USART3_IRQHandler 经 USART3_IRQ_CALLS 聚合宏调用
// ============================================================
void zigbee_rx_handler(void)
{
    uint8_t byte = (uint8_t)(ZIGBEE_UART_INST->DR & 0xFF);  // ZIGBEE_UART_INST（pin_config.h 宏）
    uint8_t i;
    uint8_t sum_calc;

    g_zigbee_link_byte_count++;  // 每收到1字节+1

    switch (rx_state)
    {
        case 0:
            // 等待同步头1: 0xAA
            if (byte == ZIGBEE_LINK_SYNC1)
                rx_state = 1;
            // 否则丢弃，保持状态0
            break;

        case 1:
            // 等待同步头2: 0x55
            if (byte == ZIGBEE_LINK_SYNC2)
            {
                rx_state = 2;
            }
            else if (byte == ZIGBEE_LINK_SYNC1)
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
            // 读取 LEN
            if (byte >= 1 && byte <= ZIGBEE_LINK_MAX_PAYLOAD)
            {
                rx_len   = byte;
                rx_index = 0;
                rx_state = 3;
            }
            else
            {
                // 非法长度（含 0）：重同步
                rx_state = 0;
            }
            break;

        case 3:
            // 读取 PAYLOAD
            rx_buf[rx_index] = byte;
            rx_index++;
            if (rx_index >= rx_len)
                rx_state = 4;
            break;

        case 4:
            // 读取 SUM 并校验
            sum_calc = (uint8_t)(ZIGBEE_LINK_SYNC1 + ZIGBEE_LINK_SYNC2 + rx_len);
            for (i = 0; i < rx_len; i++)
                sum_calc = (uint8_t)(sum_calc + rx_buf[i]);
            if (byte == sum_calc)
            {
                // 校验通过 → 入队（队列满则丢弃新帧，计数仍加）
                if (q_count < ZIGBEE_LINK_QUEUE_DEPTH)
                {
                    for (i = 0; i < rx_len; i++)
                        q_buf[q_tail][i] = rx_buf[i];
                    q_len[q_tail] = rx_len;
                    q_tail = (uint8_t)((q_tail + 1) % ZIGBEE_LINK_QUEUE_DEPTH);
                    q_count++;
                }
                g_zigbee_link_frame_count++;
            }
            // 校验失败则静默丢弃
            rx_state = 0;
            break;

        default:
            rx_state = 0;
            break;
    }
}
