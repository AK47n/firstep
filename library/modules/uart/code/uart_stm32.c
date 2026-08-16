#include "uart_stm32.h"

/* 通用串口发送（stm32 纯驱动）：转发母版 ml_uart。 */

void UART_send_char(UARTn_enum uartn, uint8_t chr)
{
    uart_sendbyte(uartn, chr);
}

void UART_send_string(UARTn_enum uartn, const char *str)
{
    uart_sendstr(uartn, (char *)str);
}

void UART_send_buffer(UARTn_enum uartn, const uint8_t *buf, uint16_t len)
{
    for (uint16_t i = 0; i < len; i++) {
        uart_sendbyte(uartn, buf[i]);
    }
}
