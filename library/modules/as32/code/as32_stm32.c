/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AS32-LoRa无线通信模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/as32-lora-wireless-communication-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include <stddef.h> /* NULL（C 库头，headfile.h 不含；UV4 必 8 错见工单 ball-detect-null-fix/01） */
#include "as32_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* AS32-TTL-100 433MHz LoRa 无线数传（stm32 纯驱动）：透传字符串收发
 * （页面 LOAR_USART_send_String/HEX 原样换算 uart_sendbyte）+ **轮询接收**
 * （页面 USART2 接收中断+空闲中断缓冲随轮询裁剪——mspm0「IRQHandler 随轮询
 * 裁剪」同判；uart_pin_init_ex 已使能 RX 中断，init 里关 RXNEIE 断流，
 * 收数时 SR RXNE 位直读 → DR）。页面全局收敛为模块静态。 */

static char as32_rx_buf[AS32_RX_BUF_MAX];
static uint16_t as32_rx_len = 0;
static uint8_t as32_rx_pending = 0; /* 有新数据待取（页面 LOAR_RX_FLAG） */

/* 排空 RX → 入缓冲（页面 IRQHandler 语义改造：SR RXNE 轮询读；
 * 满缓冲截断丢新字节——页面 (len+1)%MAX 模运算回绕覆盖首字节，人工复核
 * 修正为 cap 截断 + '\0' 收尾，notes 记录；无帧结构——行分帧归调用方） */
static void as32_drain_rx(void)
{
    while (AS32_UART_INST->SR & 0x20u) { /* USART_SR.RXNE（0x20） */
        uint8_t ch = (uint8_t)(AS32_UART_INST->DR & 0xFFu);
        if (as32_rx_len < (uint16_t)(AS32_RX_BUF_MAX - 1u)) {
            as32_rx_buf[as32_rx_len++] = (char)ch;
            as32_rx_buf[as32_rx_len] = '\0'; /* 字符串结尾补 '\0'（页面 IRQHandler） */
            as32_rx_pending = 1;
        }
        /* 满缓冲：丢弃新字节（截断保护——保首字节不被回绕覆盖） */
    }
}

void as32_init(void)
{
    /* 引脚/时钟 = uart_pin_init_ex（参数化，绑定换脚随 pin_config.h 宏）；
     * 默认 115200 后重配 9600（AS32 出厂默认——页面「默认波特率 9600」） */
    uart_pin_init_ex(AS32_UART, AS32_UART_TX_GPIO, AS32_UART_TX_Pin,
                     AS32_UART_RX_GPIO, AS32_UART_RX_Pin);
    uart_baud_config(AS32_UART, AS32_BAUDRATE);
    /* 轮询接收：关 RX 中断（CR1.RXNEIE = bit5）——页面 USART_IT_RXNE 中断
     * 使能随轮询裁剪（fingerprint/open_mv4 先例），避免与同实例 zigbee 的
     * isr.c 聚合重复消费；无中断则 as32_receive 内 SR 轮询排空 */
    AS32_UART_INST->CR1 &= (uint16_t)~0x20u;
    as32_flush();
}

void as32_send_string(const char *str)
{
    /* 页面原样：地址为空或者值为空跳出（uart_sendbyte = SR.TC 忙等） */
    while (str && *str) {
        uart_sendbyte(AS32_UART, (uint8_t)*str++);
    }
}

void as32_send_hex(const uint8_t *data, uint16_t len)
{
    while (len--) {
        uart_sendbyte(AS32_UART, *data++);
    }
}

uint16_t as32_receive(uint8_t *buf, uint16_t max_len)
{
    uint16_t n = 0;
    uint16_t i;

    as32_drain_rx();

    if (as32_rx_pending == 0) {
        return 0; /* 当前没有接收到数据（页面 Anakysis_Data 0 分支语义） */
    }
    as32_rx_pending = 0;

    if ((buf != NULL) && (max_len > 0u)) {
        n = as32_rx_len;
        if (n > (max_len - 1u)) {
            n = (uint16_t)(max_len - 1u); /* 截断保护：<= max_len-1 + '\0' */
        }
        for (i = 0; i < n; i++) {
            buf[i] = (uint8_t)as32_rx_buf[i];
        }
        buf[n] = '\0';
    }

    /* 读后清缓冲（页面 Anakysis_Data「读到即清」语义——标志位清除 +
     * Clear_LOAR_RX_BUFF） */
    as32_flush();
    return n;
}

void as32_flush(void)
{
    uint16_t i;

    for (i = 0; i < AS32_RX_BUF_MAX; i++) {
        as32_rx_buf[i] = 0;
    }
    as32_rx_len = 0;
    as32_rx_pending = 0;
}
