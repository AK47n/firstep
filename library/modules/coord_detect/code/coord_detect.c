#include "coord_detect.h"

// ==================== 环形接收缓冲区 ====================
#define COORD_RX_BUF_SIZE 512

static char rx_buf[COORD_RX_BUF_SIZE];
static volatile uint16_t rx_head = 0;
static volatile uint16_t rx_tail = 0;
volatile uint32_t coord_rx_byte_count = 0;
volatile uint32_t coord_rx_overflow = 0;
volatile uint32_t coord_rx_error = 0;

CoordResult coord_result = {0};

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

void coord_detect_init(void)
{
    // 母版 syscfg DIGIT_UART 实例（UART1, PA8/PA9, 115200, RX 中断）已由
    // SYSCFG_DL_init() 配置好波特率/引脚，这里只需打开 NVIC 中断。
    NVIC_ClearPendingIRQ(DIGIT_UART_INST_INT_IRQN);
    NVIC_EnableIRQ(DIGIT_UART_INST_INT_IRQN);
}

// 清空接收缓冲区（状态切换时调用，丢弃旧帧）
void coord_detect_flush(void)
{
    rx_head = 0;
    rx_tail = 0;
    coord_rx_byte_count = 0;
    coord_result.detected = 0;
    coord_result.updated  = 0;
    coord_result.lost_frames = 0;
}

// ==================== 中断处理 ====================

void coord_detect_rx_handler(void)
{
    // RX FIFO 单字节中断（母版 enableFIFO=false），每字节一次 IIDX_RX
    switch (DL_UART_getPendingInterrupt(DIGIT_UART_INST))
    {
    case DL_UART_IIDX_RX:
    {
        uint8_t data = DL_UART_receiveData(DIGIT_UART_INST);
        coord_rx_byte_count++;

        uint16_t next = (rx_head + 1) % COORD_RX_BUF_SIZE;
        if (next != rx_tail)
        {
            rx_buf[rx_head] = data;
            rx_head = next;
        }
        else
            coord_rx_overflow++;
        break;
    }
    case DL_UART_IIDX_OVERRUN_ERROR:
    case DL_UART_IIDX_FRAMING_ERROR:
    case DL_UART_IIDX_PARITY_ERROR:
    case DL_UART_IIDX_BREAK_ERROR:
        coord_rx_error++;
        break;
    default:
        break;
    }
}

// ==================== 环形缓冲区读字节 ====================

static int rx_read_byte(void)
{
    if (rx_head == rx_tail) return -1;
    uint8_t data = rx_buf[rx_tail];
    rx_tail = (rx_tail + 1) % COORD_RX_BUF_SIZE;
    return data;
}

// ==================== 解析一行钢珠数据 ====================

// 协议: B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2>
//  字段索引: 0=B, 1=cx, 2=cy, 3=conf, 4=x1, 5=y1, 6=x2, 7=y2
// 无检测: N

static void parse_coord_line(const char *line)
{
    char buf[16];

    // 首字符判断数据类型
    if (line[0] == 'N' && (line[1] == '\0' || line[1] == '\r' || line[1] == '\n'))
    {
        // 本帧无钢珠
        coord_result.detected = 0;
        coord_result.updated  = 1;
        coord_result.lost_frames++;
        return;
    }

    if (line[0] != 'B' || line[1] != ',')
        return;  // 未知格式，忽略

    // 解析字段（从第1个逗号后开始，即字段索引1~7）
    if (get_field(line, 1, buf, sizeof(buf)) == NULL) return;
    coord_result.cx = my_atoi(buf);

    if (get_field(line, 2, buf, sizeof(buf)) == NULL) return;
    coord_result.cy = my_atoi(buf);

    if (get_field(line, 3, buf, sizeof(buf)) == NULL) return;
    coord_result.confidence = my_atof(buf);

    if (get_field(line, 4, buf, sizeof(buf)) == NULL) return;
    coord_result.x1 = my_atoi(buf);

    if (get_field(line, 5, buf, sizeof(buf)) == NULL) return;
    coord_result.y1 = my_atoi(buf);

    if (get_field(line, 6, buf, sizeof(buf)) == NULL) return;
    coord_result.x2 = my_atoi(buf);

    if (get_field(line, 7, buf, sizeof(buf)) == NULL) return;
    coord_result.y2 = my_atoi(buf);

    coord_result.detected = 1;
    coord_result.updated  = 1;
    coord_result.lost_frames = 0;
}

// ==================== 数据解析（主循环调用） ====================

void coord_detect_parse(void)
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
                parse_coord_line(line_buf);

            line_idx = 0;
        }
        else if (ch != '\r')
        {
            if (line_idx < (int)sizeof(line_buf) - 1)
                line_buf[line_idx++] = (char)ch;
        }
    }
}
