#include "open_mv4.h"

/* OpenMV4 主控侧 UART 帧解析（mspm0 纯驱动切片，ADR 0009）：
 * 轮询接收（OPENMV4_UART 实例 enabledInterrupts 空——无 ISR 强符号，
 * fingerprint 先例）→ 行缓冲分帧（'\n' 帧界）→ `[cx,cy]`/`[pos]` 解析。
 * 页面 Openmv4DataAnalysis 只「找 '[' 找 ']'」并 printf 子串（未提取
 * 整数）——本件补数值解析；UART_1_INST_IRQHandler 中断缓冲随轮询裁剪。 */

static char open_mv4_line_buf[OPENMV4_RX_BUF_SIZE];
static uint16_t open_mv4_line_idx = 0;
static uint8_t open_mv4_line_discard = 0; /* 超长行丢弃标记（等 '\n' 复位） */
static int open_mv4_frame_cx = 0;         /* 最近解析帧结果（待取） */
static int open_mv4_frame_cy = 0;
static uint8_t open_mv4_frame_pending = 0;

/* 整数解析（页面 [%d] 形，支持正负；无 stdio；>9 位数字视为坏帧——int 溢出
 * 防护，页面坐标 ≤ 3 位）。
 * 返回 0 = 成功（*out 有效、*pp 前进到首个非数字字符）、1 = 非数字/超长。 */
static uint8_t open_mv4_parse_int(const char **pp, int *out)
{
    const char *p = *pp;
    int sign = 1;
    int val = 0;
    int digits = 0;

    if (*p == '-') {
        sign = -1;
        p++;
    }
    if ((*p < '0') || (*p > '9')) {
        return 1;
    }
    while ((*p >= '0') && (*p <= '9')) {
        val = val * 10 + (*p - '0');
        p++;
        digits++;
        if (digits > 9) {
            return 1; /* 九位以上 = 非页面坐标（int 溢出防护） */
        }
    }
    *out = val * sign;
    *pp = p;
    return 0;
}

/* 帧解析（页面 Openmv4DataAnalysis 语义 + 数值提取）：跳过任意前缀 →
 * 找 '[' → 解析 1-2 个整数（`,` 分隔，缺省单值 = 案例二循迹偏差帧，
 * cy 置 0 占位）→ 跳过尾随空格 → 必须是 ']'。
 * 返回 0 = 解析成功（cx/cy 有效）、1 = 非本件帧格式（丢弃）。 */
static uint8_t open_mv4_parse_frame(const char *line, int *cx, int *cy)
{
    const char *p = line;
    int x = 0;
    int y = 0;

    /* 找帧头 '['（页面帧带 `Maximum color block position : ` 前缀） */
    while ((*p != '\0') && (*p != '[')) {
        p++;
    }
    if (*p != '[') {
        return 1;
    }
    p++;

    if (open_mv4_parse_int(&p, &x) != 0) {
        return 1;
    }
    if (*p == ',') {
        p++;
        if (open_mv4_parse_int(&p, &y) != 0) {
            return 1;
        }
    } else {
        y = 0; /* 单值帧 [%d]（页面案例二循迹偏差）——cy 占位 0 */
    }
    if (*p != ']') {
        return 1; /* 三整数/尾随垃圾 = 非本件帧格式（页面格式无空格） */
    }

    *cx = x;
    *cy = y;
    return 0;
}

/* 排空 RX FIFO 并按行分帧（轮询——9600 波特每字节 ~1.04ms，主循环节拍
 * 内调用 read_frame 即完成排空；'\r' 忽略（页面帧 `\r\n` 结尾））。 */
static void open_mv4_drain_rx(void)
{
    uint8_t ch;

    while (DL_UART_isRXFIFOEmpty(OPENMV4_UART_INST) == false) {
        ch = DL_UART_receiveData(OPENMV4_UART_INST);
        if (ch == '\n') {
            open_mv4_line_buf[open_mv4_line_idx] = '\0';
            if ((open_mv4_line_discard == 0) && (open_mv4_line_idx > 0) &&
                (open_mv4_parse_frame(open_mv4_line_buf,
                                      &open_mv4_frame_cx,
                                      &open_mv4_frame_cy) == 0)) {
                open_mv4_frame_pending = 1;
            }
            open_mv4_line_idx = 0;
            open_mv4_line_discard = 0;
        } else if (ch != '\r') {
            if (open_mv4_line_idx < (uint16_t)(OPENMV4_RX_BUF_SIZE - 1u)) {
                open_mv4_line_buf[open_mv4_line_idx++] = (char)ch;
            } else {
                open_mv4_line_discard = 1; /* 超长行：余下字符丢弃至帧界 */
            }
        }
    }
}

void open_mv4_init(void)
{
    /* 无 NVIC 使能（轮询接收，页面 OpenMV4_usart_config 随轮询裁剪）；
     * UART 引脚/波特率由 SYSCFG_DL_init() 配置 */
    open_mv4_flush();
}

void open_mv4_flush(void)
{
    open_mv4_line_idx = 0;
    open_mv4_line_discard = 0;
    open_mv4_line_buf[0] = '\0';
    open_mv4_frame_pending = 0;
}

uint8_t open_mv4_read_frame(int *cx, int *cy, float *confidence)
{
    open_mv4_drain_rx();

    if (open_mv4_frame_pending == 0) {
        return 1; /* 暂无完整帧（含坏帧丢弃后） */
    }
    open_mv4_frame_pending = 0;
    if (cx != NULL) {
        *cx = open_mv4_frame_cx;
    }
    if (cy != NULL) {
        *cy = open_mv4_frame_cy;
    }
    if (confidence != NULL) {
        /* 页面帧格式无置信度字段——OpenMV 侧阈值命中才发送，取 1.0 */
        *confidence = OPENMV4_CONFIDENCE;
    }
    return 0;
}
