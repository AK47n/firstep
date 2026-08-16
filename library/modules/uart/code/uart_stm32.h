#ifndef UART_STM32_H
#define UART_STM32_H

#include "headfile.h"  // ml_uart：UARTn_enum / uart_sendbyte / uart_sendstr
#include <stdint.h>

/* 通用串口发送（stm32）：实例用 UARTn_enum 选择（UART_1/2/3）。
 * 发送前需由骨架或调用方完成 uart_pin_init / uart_init。 */

void UART_send_string(UARTn_enum uartn, const char *str);
void UART_send_char(UARTn_enum uartn, uint8_t chr);
void UART_send_buffer(UARTn_enum uartn, const uint8_t *buf, uint16_t len);

#endif // UART_STM32_H
