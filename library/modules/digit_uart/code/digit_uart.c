#include "headfile.h"
#include "digit_uart.h"
#include <stddef.h>

// ==================== 环形接收缓冲区 ====================
#define RX_BUF_SIZE 1024

static char rx_buf[RX_BUF_SIZE];
static volatile uint16_t rx_head = 0;
static volatile uint16_t rx_tail = 0;
volatile uint32_t rx_byte_count = 0;
volatile uint32_t rx_overflow = 0;
volatile uint32_t rx_error = 0;

DigitResult digit_result = {0};

// ==================== 简易字符串转换 ====================

static int my_atoi(const char *s)
{
    int n = 0, sign = 1;
    if (*s == '-') { sign = -1; s++; }
    while (*s >= '0' && *s <= '9') { n = n * 10 + (*s++ - '0'); }
    return n * sign;
}

static float my_atof(const char *s)
{
    float n = 0.0f, frac = 0.0f;
    int sign = 1, div = 1;
    if (*s == '-') { sign = -1; s++; }
    while (*s >= '0' && *s <= '9') { n = n * 10.0f + (*s++ - '0'); }
    if (*s == '.')
    {
        s++;
        while (*s >= '0' && *s <= '9') { frac = frac * 10.0f + (*s++ - '0'); div *= 10; }
    }
    return sign * (n + frac / div);
}

// ==================== CSV 字段提取（不修改原字符串） ====================
static char* get_field(const char *line, int n, char *buf, int buf_size)
{
    int i = 0;
    const char *p = line;

    while (i < n && *p)
    {
        if (*p == ',') i++;
        p++;
    }
    if (*p == '\0') return NULL;

    int j = 0;
    while (*p && *p != ',' && *p != '\r' && *p != '\n' && j < buf_size - 1)
        buf[j++] = *p++;
    buf[j] = '\0';
    return buf;
}

// ==================== 初始化 ====================

void digit_uart_init(void)
{
    uart_init(UART_1, 115200, 0);
}

// 清空K230接收缓冲区（识别窗口开启时调用，丢弃旧帧）
void digit_uart_flush(void)
{
    rx_head = 0;
    rx_tail = 0;
    rx_byte_count = 0;
    digit_result.count   = 0;
    digit_result.updated = 0;
}

// ==================== 中断处理 ====================

void digit_uart_rx_handler(void)
{
    while (USART1->SR & (0x20 | 0x08))
    {
        if (USART1->SR & 0x08)
            rx_error++;

        if (USART1->SR & 0x20)
        {
            uint8_t data = USART1->DR;
            rx_byte_count++;

            uint16_t next = (rx_head + 1) % RX_BUF_SIZE;
            if (next != rx_tail)
            {
                rx_buf[rx_head] = data;
                rx_head = next;
            }
            else
                rx_overflow++;
        }
        else
        {
            uint8_t dummy = USART1->DR;
            (void)dummy;
        }
    }
}

// ==================== 数据解析 ====================

static int rx_read_byte(void)
{
    if (rx_head == rx_tail) return -1;
    uint8_t data = rx_buf[rx_tail];
    rx_tail = (rx_tail + 1) % RX_BUF_SIZE;
    return data;
}

// 解析数据行 "数字,置信度,..." → 存入 digit_result.digits[idx]
static void parse_digit_line(char *line, int idx)
{
    char buf[16];

    if (idx >= MAX_DIGITS) return;
    DigitInfo *d = &digit_result.digits[idx];

    if (get_field(line, 0, buf, sizeof(buf)) == NULL) return;
    {
        int i = 0;
        char *s = buf;
        while (*s && i < (int)sizeof(d->label) - 1)
            d->label[i++] = *s++;
        d->label[i] = '\0';
    }

    if (get_field(line, 1, buf, sizeof(buf)) == NULL) return;
    d->confidence = my_atof(buf);

    if (get_field(line, 6, buf, sizeof(buf)) == NULL) return;
    d->cx = my_atoi(buf);

    if (get_field(line, 7, buf, sizeof(buf)) == NULL) return;
    d->cy = my_atoi(buf);
}

void digit_uart_parse(void)
{
    static char line_buf[128];
    static int line_idx = 0;
    static int digit_idx = 0;      // 当前帧内第几个目标
    static int in_frame = 0;       // 是否已收到帧头
    int ch;

    // ===== 批量最佳帧：一次 parse 可能处理多帧，保留数字最多的那帧 =====
    DigitResult best_in_batch;
    best_in_batch.count = 0;
    best_in_batch.updated = 0;
    int best_count = 0;  // 最佳帧的数字数量

    // 辅助：将当前帧与最佳帧比较
    #define SAVE_IF_BETTER() \
        do { \
            if (in_frame && digit_result.count > best_count) { \
                best_in_batch = digit_result; \
                best_count = digit_result.count; \
            } \
        } while(0)

    while ((ch = rx_read_byte()) != -1)
    {
        if (ch == '\n')
        {
            line_buf[line_idx] = '\0';

            // 帧头 "--- frame N | M targets ---"
            if (line_buf[0] == '-' && line_buf[1] == '-' && line_buf[2] == '-')
            {
                // 上一帧结束 → 参与比较
                SAVE_IF_BETTER();

                digit_idx = 0;
                in_frame = 1;
                digit_result.count = 0;
                digit_result.updated = 0;
            }
            else if (line_buf[0] != '\0' && line_buf[0] != '\r')
            {
                // 数据行
                parse_digit_line(line_buf, digit_idx);
                digit_idx++;
                if (digit_idx > MAX_DIGITS) digit_idx = MAX_DIGITS;
                digit_result.count = digit_idx;
                digit_result.updated = 1;
            }
            // 空行 → 一帧结束
            else if (line_buf[0] == '\0' || line_buf[0] == '\r')
            {
                if (in_frame && digit_result.count > 0)
                {
                    digit_result.updated = 1;
                }
                // 帧结束 → 参与比较
                SAVE_IF_BETTER();
                in_frame = 0;
            }

            line_idx = 0;
        }
        else if (ch != '\r')
        {
            if (line_idx < (int)sizeof(line_buf) - 1)
                line_buf[line_idx++] = (char)ch;
        }
    }

    // 处理缓冲区末尾可能存在的未完成帧
    SAVE_IF_BETTER();

    // 用批量中的最佳帧替换最终结果
    if (best_count > 0)
    {
        digit_result = best_in_batch;
    }

    #undef SAVE_IF_BETTER
}
