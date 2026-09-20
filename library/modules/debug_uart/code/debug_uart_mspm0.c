#include "debug_uart_mspm0.h"

// ============================================================
//  DEBUG_UART 初始化：SYSCFG_DL_init() 已配好 DEBUG_UART（UART2,
//  PA23(TX)/PA22(RX), 115200, RX 中断），这里只开 NVIC。
// ============================================================
void debug_uart_init(void)
{
    NVIC_ClearPendingIRQ(DEBUG_UART_INST_INT_IRQN);
    NVIC_EnableIRQ(DEBUG_UART_INST_INT_IRQN);
}

// ============================================================
//  发送字符串 (阻塞)
// ============================================================
void debug_uart_send(const char *str)
{
    while (*str)
    {
        DL_UART_transmitDataBlocking(DEBUG_UART_INST, (uint8_t)*str);
        str++;
    }
}

// ============================================================
//  调试命令接收：单字符/短命令，回车结尾（与 stm32 版同缓冲形态）
// ============================================================
static char    cmd_buf[8];
static uint8_t cmd_idx = 0;

void debug_uart_rx_handler(void)
{
    uint8_t byte;

    switch (DL_UART_getPendingInterrupt(DEBUG_UART_INST))
    {
    case DL_UART_IIDX_RX:
        byte = DL_UART_receiveData(DEBUG_UART_INST);
        break;
    default:
        return;
    }

    char c = (char)byte;
    if (c == '\r' || c == '\n')
    {
        if (cmd_idx > 0)
        {
            cmd_buf[cmd_idx] = '\0';
            cmd_idx = 0;
        }
    }
    else if (cmd_idx < sizeof(cmd_buf) - 1)
    {
        cmd_buf[cmd_idx++] = c;
    }
}

// DEBUG_UART_INST_IRQHandler = UART2_IRQHandler（母版 SysConfig 宏）
void DEBUG_UART_INST_IRQHandler(void)
{
    debug_uart_rx_handler();
}

// ============================================================
//  主循环调用：mspm0 侧只回显已收命令——LED/蜂鸣器命令的执行
//  请用 led / beep 模块（纯调试驱动不拖业务模块依赖）。
// ============================================================
void debug_cmd_poll(void)
{
    if (cmd_buf[0] == '\0') return;

    DEBUG_PRINTF("CMD: %s\r\n", cmd_buf);
    cmd_buf[0] = '\0';
}

// ============================================================
//  命令台接口（工单 module-hwcheck/06）
//
//  硬件检测程序按库内配方给每件器件挂一个复测字符，它需要先看一眼收到的
//  命令再决定认不认领：认领（配方命令 / 帮助）才 consume，其余一律不碰，
//  留给上面的 debug_cmd_poll()（本平台那条路是原样回显）。
//
//  peek 只读、consume 才清空。命令粒度同样是首字符（与 debug_cmd_poll 同款）。
// ============================================================
const char *debug_cmd_peek(void)
{
    return cmd_buf;     // 没有完整命令时是空串（首字符 '\0'）
}

void debug_cmd_consume(void)
{
    cmd_buf[0] = '\0';  // 与 debug_cmd_poll() 处理完那一下同一写法
}
