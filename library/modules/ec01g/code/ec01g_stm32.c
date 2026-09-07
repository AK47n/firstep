/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《EC-01G NB-IoT+GPS模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/ec01g-nbiot-gps-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include <stddef.h> /* NULL（headfile.h 不含 stddef——ball-detect-null-fix/01 先例） */
#include "ec01g_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* EC-01G NB-IoT+GPS（stm32 纯驱动，AT 指令透传底座）：
 * 页内驱动（bsp_ec01g.c/h）走 USART2 中断（EC01G_USART_IRQHandler：
 * RXNE + IDLE、(len+1)%2096 环形回绕、IDLE 在当前位写 '\0'）+ 单 FLAG 缓冲 +
 * HTTP 天气 demo（EC01G_Seniverse_Init/Get_Weather_Data/Hex_To_Text/
 * Search_Data/Weather_Data_Analysis——心知天气密钥/城市宏/JSON 应用层）；
 * 本件改**线性缓冲 + 超限截断**（同 esp01s 判）：rx_handler 逐字节入
 * EC01G_RX_BUF_SIZE 缓冲（满丢新字节——回绕修正）+ 按长度 NUL 终结（IDLE
 * 断串修正）；发送/应答匹配原语化（页面 EC01G_Send_Cmd 去 goto/ack/printf）；
 * HTTP 天气/JSON/hex 解码 demo 与 GPS（页面无代码）归范围外——模块只出 AT
 * 底座原语。 */

static volatile uint8_t _rx[EC01G_RX_BUF_SIZE]; /* 应答缓冲（线性 + 截断保护） */
static volatile uint16_t _rx_len = 0;           /* 已收字节数（NUL 终结于 _rx[_rx_len]） */

/* 有界子串匹配（页面 strstr 原语化——零标准库；页面 Search_Data 无界扫修正
 * 同口径：所有扫描带上限） */
static uint8_t _buf_contains(const char *needle)
{
    uint16_t i, j, nlen;

    for (nlen = 0; needle[nlen]; nlen++) {
        /* 求长度 */
    }
    if (nlen == 0) {
        return 1u;
    }
    for (i = 0; i + (uint16_t)nlen <= _rx_len; i++) {
        for (j = 0; j < nlen; j++) {
            if ((uint8_t)needle[j] != _rx[i + j]) {
                break;
            }
        }
        if (j == nlen) {
            return 1u;
        }
    }
    return 0u;
}

void ec01g_rx_handler(void)
{
    while (EC01G_UART_INST->SR & 0x20u) { /* USART_SR.RXNE（0x20） */
        uint8_t byte = (uint8_t)(EC01G_UART_INST->DR & 0xFFu);
        if (_rx_len < (EC01G_RX_BUF_SIZE - 1u)) {
            _rx[_rx_len++] = byte;
            _rx[_rx_len] = 0; /* 按长度 NUL 终结（页面 IDLE '\0' 断串修正） */
        }
        /* 满缓冲：截断保护——丢弃新字节（页面 (len+1)%2096 回绕覆盖首字节修正） */
    }
}

void ec01g_init(void)
{
    uart_pin_init_ex(EC01G_UART, EC01G_UART_TX_GPIO, EC01G_UART_TX_Pin,
                     EC01G_UART_RX_GPIO, EC01G_UART_RX_Pin);
    uart_baud_config(EC01G_UART, EC01G_BAUDRATE); /* 9600：EC-01G 出厂默认 */
    _rx_len = 0;
    _rx[0] = 0;
}

uint8_t ec01g_send_cmd(const char *cmd)
{
    uint32_t timeout = EC01G_CMD_TIMEOUT_MS;

    if (cmd == NULL) {
        return 0u; /* 空指针保护（页面 Get_Weather_Data rev_buff=NULL 崩溃修正同源） */
    }
    _rx_len = 0; /* 发前清缓冲：防陈旧匹配（页面 Send_Cmd 前清 FLAG 同构） */
    _rx[0] = 0;
    ec01g_send_string(cmd);
    ec01g_send_string("\r\n");

    while (1) {
        if (_buf_contains("OK")) {
            return 1u; /* 应答命中 */
        }
        if (timeout == 0) {
            return 0u; /* 超时（页面 cnt×waitms 语义——本件一轮超时） */
        }
        delay_ms(1);
        timeout--;
    }
}

void ec01g_send_string(const char *s)
{
    if (s == NULL) {
        return; /* 空指针保护 */
    }
    while (*s) {
        uart_sendbyte(EC01G_UART, (uint8_t)*s++);
    }
}

uint8_t ec01g_available(void)
{
    return (_rx_len > 0) ? 1u : 0u;
}

uint16_t ec01g_receive(uint8_t *buf, uint16_t max_len)
{
    uint16_t count = 0;
    uint16_t i;

    if (buf == NULL || max_len == 0u) {
        return 0u; /* 空指针保护 */
    }
    for (i = 0; i < _rx_len && count < max_len; i++) {
        buf[count++] = _rx[i];
    }
    _rx_len = 0;
    _rx[0] = 0;
    return count;
}
