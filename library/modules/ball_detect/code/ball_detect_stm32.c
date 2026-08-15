#include <stddef.h>  // NULL（C 库头，headfile.h 不含；UV4 必 8 错见工单 ball-detect-null-fix/01）
#include "headfile.h"
#include "ball_detect_stm32.h"
#include "pin_config.h"

// ==================== 环形接收缓冲区 ====================
#define BALL_RX_BUF_SIZE 512

static char rx_buf[BALL_RX_BUF_SIZE];
static volatile uint16_t rx_head = 0;
static volatile uint16_t rx_tail = 0;
volatile uint32_t ball_rx_byte_count = 0;
volatile uint32_t ball_rx_overflow = 0;
volatile uint32_t ball_rx_error = 0;

BallResult ball_result = {0};

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

void ball_detect_init(void)
{
    uart_pin_init_ex(BALL_DETECT_UART, BALL_DETECT_UART_TX_GPIO, BALL_DETECT_UART_TX_Pin,
                     BALL_DETECT_UART_RX_GPIO, BALL_DETECT_UART_RX_Pin);
}

// 清空接收缓冲区（状态切换时调用，丢弃旧帧）
void ball_detect_flush(void)
{
    rx_head = 0;
    rx_tail = 0;
    ball_rx_byte_count = 0;
    ball_result.detected = 0;
    ball_result.updated  = 0;
    ball_result.lost_frames = 0;
}

// ==================== 中断处理 ====================

void ball_detect_rx_handler(void)
{
    while (BALL_DETECT_UART_INST->SR & (0x20 | 0x08))
    {
        if (BALL_DETECT_UART_INST->SR & 0x08)
            ball_rx_error++;

        if (BALL_DETECT_UART_INST->SR & 0x20)
        {
            uint8_t data = BALL_DETECT_UART_INST->DR;
            ball_rx_byte_count++;

            uint16_t next = (rx_head + 1) % BALL_RX_BUF_SIZE;
            if (next != rx_tail)
            {
                rx_buf[rx_head] = data;
                rx_head = next;
            }
            else
                ball_rx_overflow++;
        }
        else
        {
            uint8_t dummy = BALL_DETECT_UART_INST->DR;
            (void)dummy;
        }
    }
}

// ==================== 环形缓冲区读字节 ====================

static int rx_read_byte(void)
{
    if (rx_head == rx_tail) return -1;
    uint8_t data = rx_buf[rx_tail];
    rx_tail = (rx_tail + 1) % BALL_RX_BUF_SIZE;
    return data;
}

// ==================== 解析一行钢珠数据 ====================

// 协议: B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2>
//  字段索引: 0=B, 1=cx, 2=cy, 3=conf, 4=x1, 5=y1, 6=x2, 7=y2
// 无检测: N

static void parse_ball_line(const char *line)
{
    char buf[16];

    // 首字符判断数据类型
    if (line[0] == 'N' && (line[1] == '\0' || line[1] == '\r' || line[1] == '\n'))
    {
        // 本帧无钢珠
        ball_result.detected = 0;
        ball_result.updated  = 1;
        ball_result.lost_frames++;
        return;
    }

    if (line[0] != 'B' || line[1] != ',')
        return;  // 未知格式，忽略

    // 解析字段（从第1个逗号后开始，即字段索引1~7）
    if (get_field(line, 1, buf, sizeof(buf)) == NULL) return;
    ball_result.cx = my_atoi(buf);

    if (get_field(line, 2, buf, sizeof(buf)) == NULL) return;
    ball_result.cy = my_atoi(buf);

    if (get_field(line, 3, buf, sizeof(buf)) == NULL) return;
    ball_result.confidence = my_atof(buf);

    if (get_field(line, 4, buf, sizeof(buf)) == NULL) return;
    ball_result.x1 = my_atoi(buf);

    if (get_field(line, 5, buf, sizeof(buf)) == NULL) return;
    ball_result.y1 = my_atoi(buf);

    if (get_field(line, 6, buf, sizeof(buf)) == NULL) return;
    ball_result.x2 = my_atoi(buf);

    if (get_field(line, 7, buf, sizeof(buf)) == NULL) return;
    ball_result.y2 = my_atoi(buf);

    ball_result.detected = 1;
    ball_result.updated  = 1;
    ball_result.lost_frames = 0;
}

// ==================== 数据解析（主循环调用） ====================

void ball_detect_parse(void)
{
    static char line_buf[64];
    static int line_idx = 0;
    int ch;

    while ((ch = rx_read_byte()) != -1)
    {
        if (ch == '\n')
        {
            line_buf[line_idx] = '\0';

            if (line_buf[0] != '\0' && line_buf[0] != '\r')
                parse_ball_line(line_buf);

            line_idx = 0;
        }
        else if (ch != '\r')
        {
            if (line_idx < (int)sizeof(line_buf) - 1)
                line_buf[line_idx++] = (char)ch;
        }
    }
}
