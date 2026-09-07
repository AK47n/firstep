/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《ESP-01S WiFi模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/esp01s-wifi-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "esp01s_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* ESP-01S WiFi（stm32 纯驱动，AT 指令透传）：
 * 页内驱动（bsp_esp01s.c/h）走 USART2 中断（WIFI_USART_IRQHandler：
 * RXNE + IDLE、(len+1)%200 环形回绕、IDLE 在当前位写 '\0'）+ 单 FLAG 缓冲；
 * 本件改**线性缓冲 + 超限截断**：rx_handler 逐字节入 ESP01S_RX_BUF_SIZE
 * 缓冲（满丢新字节——回绕覆盖首字节修正）+ 按长度 NUL 终结（IDLE 断串
 * 修正）；发送/应答匹配原语化（页面 WIFI_Send_Cmd 去 goto/ack/printf）；
 * MQTT/阿里云/JSON/hmacsha1 demo 与 AT 模板（CWMODE/CWSAP/CIPSERVER/
 * CIPSEND）归骨架/范围外——模块只出串口透传原语 + +IPD 解析原语。 */

static volatile uint8_t _rx[ESP01S_RX_BUF_SIZE]; /* 应答缓冲（线性 + 截断保护） */
static volatile uint16_t _rx_len = 0;            /* 已收字节数（NUL 终结于 _rx[_rx_len]） */

/* 有界子串匹配（页面 strstr 原语化——零标准库） */
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

void esp01s_rx_handler(void)
{
    while (ESP01S_UART_INST->SR & 0x20u) { /* USART_SR.RXNE（0x20） */
        uint8_t byte = (uint8_t)(ESP01S_UART_INST->DR & 0xFFu);
        if (_rx_len < (ESP01S_RX_BUF_SIZE - 1u)) {
            _rx[_rx_len++] = byte;
            _rx[_rx_len] = 0; /* 按长度 NUL 终结（页面 IDLE '\0' 断串修正） */
        }
        /* 满缓冲：截断保护——丢弃新字节（页面 (len+1)%200 回绕覆盖首字节修正） */
    }
}

void esp01s_init(void)
{
    uart_pin_init_ex(ESP01S_UART, ESP01S_UART_TX_GPIO, ESP01S_UART_TX_Pin,
                     ESP01S_UART_RX_GPIO, ESP01S_UART_RX_Pin);
    uart_baud_config(ESP01S_UART, ESP01S_BAUDRATE); /* 115200：ESP-01S 出厂默认 */
    _rx_len = 0;
    _rx[0] = 0;
}

uint8_t esp01s_send_cmd(const char *cmd)
{
    uint32_t timeout = ESP01S_CMD_TIMEOUT_MS;

    _rx_len = 0; /* 发前清缓冲：防陈旧匹配（页面 Send_Cmd 前清 FLAG 同构） */
    _rx[0] = 0;
    esp01s_send_string(cmd);
    esp01s_send_string("\r\n");

    while (1) {
        if (_buf_contains("OK")) {
            return 1u; /* 应答命中 */
        }
        if (timeout == 0) {
            return 0u; /* 超时（页面 cnt×waitms 有界重试语义——本件一轮超时） */
        }
        delay_ms(1);
        timeout--;
    }
}

void esp01s_send_string(const char *s)
{
    while (s && *s) {
        uart_sendbyte(ESP01S_UART, (uint8_t)*s++);
    }
}

uint8_t esp01s_available(void)
{
    return (_rx_len > 0) ? 1u : 0u;
}

uint16_t esp01s_receive(uint8_t *buf, uint16_t max_len)
{
    uint16_t count = 0;
    uint16_t i;

    for (i = 0; i < _rx_len && count < max_len; i++) {
        buf[count++] = _rx[i];
    }
    _rx_len = 0;
    _rx[0] = 0;
    return count;
}

uint8_t esp01s_parse_ipd(uint8_t *id, uint16_t *len, uint8_t *out, uint16_t max)
{
    uint16_t i = 0, j;
    uint16_t olen = 0;
    uint8_t idv = 0;

    if (max < 1u) {
        return 1u;
    }
    /* 定位 "+IPD,"（有界扫） */
    for (i = 0; i + 5u <= _rx_len; i++) {
        const char *sig = "+IPD,";
        for (j = 0; j < 5u; j++) {
            if ((uint8_t)sig[j] != _rx[i + j]) {
                break;
            }
        }
        if (j == 5u) {
            break;
        }
    }
    if (i + 5u > _rx_len) {
        return 1u; /* 无 +IPD 帧（页面 strstr 未命中语义） */
    }
    i += 5u;
    /* id 客户端号（有界） */
    while (i < _rx_len && _rx[i] >= '0' && _rx[i] <= '9') {
        idv = (uint8_t)(idv * 10u + (uint8_t)(_rx[i] - '0'));
        i++;
    }
    if (i >= _rx_len || _rx[i] != ',') {
        return 1u;
    }
    i++;
    /* len 数据长度（有界） */
    while (i < _rx_len && _rx[i] >= '0' && _rx[i] <= '9') {
        i++;
    }
    if (i >= _rx_len || _rx[i] != ':') {
        return 1u;
    }
    i++;
    /* 载荷拷贝（至多 max-1 + NUL 终结；页面 buff[50] 截断 200 数据修正） */
    while (i < _rx_len && _rx[i] != '\r' && _rx[i] != '\n') {
        if (olen < max - 1u) {
            out[olen++] = _rx[i];
        }
        i++;
    }
    out[olen] = 0;
    if (id) {
        *id = idv;
    }
    if (len) {
        *len = olen;
    }
    return 0u;
}
