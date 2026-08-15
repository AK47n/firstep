/* ============================================================
 * UART 接收中断聚合（ADR 0012 工单 02）：每个 USARTx_IRQHandler 调
 * pin_config.h 渲染的 USARTx_IRQ_CALLS 聚合宏——宏按各 UART 角色绑定
 * 实例分组各模块 rx_handler 调用（默认 UART_1 = DIGIT+BALL+UWB 共享、
 * UART_2 = DEBUG、UART_3 = ZIGBEE；绑定换实例后由生成器重分组）。
 *
 * __weak 空兜底：未选模块的 handler 缺失时链接不炸（调用进空函数，
 * 收字节静默丢弃）——选中模块的强定义覆盖弱兜底（宁严勿假绿：收字节
 * 必进真实 handler，此前无 isr.c = 字节进启动文件弱 handler 的假绿）。
 * ============================================================ */
#include "pin_config.h"

__weak void digit_uart_rx_handler(void) {}
__weak void ball_detect_rx_handler(void) {}
__weak void debug_uart_rx_handler(void) {}
__weak void uwb_rx_handler(void) {}
__weak void zigbee_rx_handler(void) {}

void USART1_IRQHandler(void) { USART1_IRQ_CALLS }
void USART2_IRQHandler(void) { USART2_IRQ_CALLS }
void USART3_IRQHandler(void) { USART3_IRQ_CALLS }
