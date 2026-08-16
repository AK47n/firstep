#ifndef UART_H
#define UART_H

#include "ti_msp_dl_config.h"
#include <stdint.h>

void UART_send_string(UART_Regs *uart, const char *str);
void UART_send_char(UART_Regs *uart, uint8_t chr);
void UART_send_buffer(UART_Regs *uart, const uint8_t *buf, uint16_t len);

#endif /* UART_H */
