#include "headfile.h"
#include "debug_uart.h"
#include "config.h"

// ============================================================
//  UART2 初始化 (PA2=TX, PA3=RX, 115200bps)
// ============================================================
void debug_uart_init(void)
{
    // UART2 在 APB1 上
    uart_init(UART_2, 115200, 0);  // priority=0，不开接收中断
}

// ============================================================
//  发送字符串 (阻塞)
// ============================================================
void debug_uart_send(const char *str)
{
    uart_sendstr(UART_2, (char*)str);
}

// ============================================================
//  调试命令接收与解析
//
//  命令格式 (单字符，回车结尾):
//    r / R    → 红灯亮，其余灭 (模拟关闭)
//    y / Y    → 黄灯亮，其余灭 (模拟远区)
//    g / G    → 绿灯亮，其余灭 (模拟开启)
//    o / O    → 全灭
//    b<N>     → 蜂鸣器响 N ms (如 b50, b200)
// ============================================================

static char  cmd_buf[8];
static uint8_t cmd_idx = 0;

// USART2 ISR 调用：收一个字节放入命令缓冲
void debug_uart_rx_handler(void)
{
    char c = (char)(USART2->DR & 0xFF);

    if (c == '\r' || c == '\n')
    {
        if (cmd_idx > 0)
        {
            cmd_buf[cmd_idx] = '\0';
            cmd_idx = 0;
            // 回调主循环解析 (设置标志)
            // 这里直接解析也行，但为了简单，在 poll 里解析
            // 把已收命令暂存，poll 中处理
        }
    }
    else if (cmd_idx < sizeof(cmd_buf) - 1)
    {
        cmd_buf[cmd_idx++] = c;
    }
}

// 主循环调用：解析并执行命令
void debug_cmd_poll(void)
{
    if (cmd_buf[0] == '\0') return;

    char c = cmd_buf[0];

    if (c == 'r' || c == 'R')
    {
        gpio_set(LED_PORT, LED_RED_PIN, 1);      // 红灯
        gpio_set(LED_PORT, LED_YELLOW_PIN, 0);
        gpio_set(LED_PORT, LED_GREEN_PIN, 0);
        DEBUG_PRINTF("LED: RED (lock)\r\n");
    }
    else if (c == 'y' || c == 'Y')
    {
        gpio_set(LED_PORT, LED_RED_PIN, 0);
        gpio_set(LED_PORT, LED_YELLOW_PIN, 1);   // 黄灯
        gpio_set(LED_PORT, LED_GREEN_PIN, 0);
        DEBUG_PRINTF("LED: YELLOW (welcome)\r\n");
    }
    else if (c == 'g' || c == 'G')
    {
        gpio_set(LED_PORT, LED_RED_PIN, 0);
        gpio_set(LED_PORT, LED_YELLOW_PIN, 0);
        gpio_set(LED_PORT, LED_GREEN_PIN, 1);    // 绿灯
        DEBUG_PRINTF("LED: GREEN (unlock)\r\n");
    }
    else if (c == 'o' || c == 'O')
    {
        gpio_set(LED_PORT, LED_RED_PIN, 0);
        gpio_set(LED_PORT, LED_YELLOW_PIN, 0);
        gpio_set(LED_PORT, LED_GREEN_PIN, 0);    // 全灭
        DEBUG_PRINTF("LED: OFF\r\n");
    }
    else if (c == 'b' || c == 'B')
    {
        // b50 → 蜂鸣器响 50ms
        uint32_t ms = 0;
        for (uint8_t i = 1; cmd_buf[i] >= '0' && cmd_buf[i] <= '9'; i++)
            ms = ms * 10 + (cmd_buf[i] - '0');
        if (ms > 0 && ms <= 5000)
        {
            gpio_set(BUZZER_GPIO, BUZZER_PIN, 0);  // 低电平=响
            delay_ms(ms);
            gpio_set(BUZZER_GPIO, BUZZER_PIN, 1);  // 高电平=关
            DEBUG_PRINTF("BUZZER: %lums\r\n", ms);
        }
    }
    else
    {
        DEBUG_PRINTF("? r/g/y/o/b<N>\r\n");
    }

    cmd_buf[0] = '\0';  // 已处理
}
