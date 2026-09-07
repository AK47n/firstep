/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《NEO-6M GPS模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/neo-6m-gps-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "neo_6m_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* NEO-6M GPS 定位（stm32 纯驱动，真实串口 9600 + NMEA 帧识别）：
 * 页内驱动（bsp_gps.c/h）走 RS232/USART2 中断（BSP_GPS_IRQHandler：'$' 重置
 * LEN → 逐字节入 GPSRX_BUFF[255] → [4]=='M'&&[5]=='C' + '\n' 整帧 memcpy 入
 * Save_Data.GPS_Buffer[80]）+ main 循环 parseGpsBuffer 字段解析；本件改
 * **中断收帧状态机 + 服务函数解析**：'$' 开始新帧、'\n' 行尾校验
 * 语句 ID（$+GP|GN+RMC）整帧入帧存储 + 置位，neo_6m_get_position 解析
 * 字段 3/4/5/6 出十进制度（页面原样字符串字段换算）；页面 main 演示/
 * errorLog 死循环/printGpsBuffer/printf 全剔除。 */

static volatile uint8_t _rx[NEO_6M_RX_BUF_SIZE];         /* 收帧缓冲（256，截断保护） */
static volatile uint16_t _rx_len = 0;                    /* 当前帧已有字节数 */
static volatile uint8_t _frame[NEO_6M_FRAME_BUF_SIZE];   /* 完整 GPRMC 帧存储 */
static volatile uint8_t _frame_len = 0;
static volatile uint8_t _frame_flag = 0;                 /* 1 = 有新完整帧待读 */

/* GPRMC/GNRMC 语句 ID 判定（'$' 后 1-5 字节：GP|GN + RMC——页面只验 [4]/[5] 修正） */
static uint8_t _is_rmc_frame(void)
{
    if (_rx_len < 7u) {
        return 0u;
    }
    if (_rx[1] != 'G') {
        return 0u;
    }
    /* [2] = P（GPRMC）或 N（GNRMC），[3..5] = RMC */
    if (_rx[2] != 'P' && _rx[2] != 'N') {
        return 0u;
    }
    return (_rx[3] == 'R' && _rx[4] == 'M' && _rx[5] == 'C') ? 1u : 0u;
}

void neo_6m_rx_handler(void)
{
    while (NEO_6M_UART_INST->SR & 0x20u) { /* USART_SR.RXNE（0x20） */
        uint8_t byte = (uint8_t)(NEO_6M_UART_INST->DR & 0xFFu);

        if (byte == '$') {
            _rx_len = 0; /* 新帧起点（页面原样） */
        }
        if (_rx_len < (NEO_6M_RX_BUF_SIZE - 1u)) {
            _rx[_rx_len++] = byte;
        }
        /* 缓冲满：截断保护（页面 GPSRX_LEN=255 后下标 255 越界修正——
         * 超长帧后续字节丢弃，'\n' 行尾校验被 _is_rmc_frame 拒绝丢弃） */
        if (byte == '\n') {
            if (_is_rmc_frame()) {
                uint16_t copy_len = _rx_len;
                uint16_t i;
                if (copy_len >= NEO_6M_FRAME_BUF_SIZE) {
                    copy_len = NEO_6M_FRAME_BUF_SIZE - 1u; /* 页面 memcpy 无长度检查修正 */
                }
                for (i = 0; i < copy_len; i++) {
                    _frame[i] = _rx[i];
                }
                _frame_len = (uint8_t)copy_len;
                _frame_flag = 1;
            }
            _rx_len = 0; /* 本帧结束，等下一个 '$'（页面原样） */
        }
    }
}

void neo_6m_init(void)
{
    uart_pin_init_ex(NEO_6M_UART, NEO_6M_UART_TX_GPIO, NEO_6M_UART_TX_Pin,
                     NEO_6M_UART_RX_GPIO, NEO_6M_UART_RX_Pin);
    uart_baud_config(NEO_6M_UART, NEO_6M_BAUDRATE); /* 9600：NEO-6M 出厂默认 */
    neo_6m_clear();
}

uint8_t neo_6m_read_frame(void)
{
    if (_frame_flag == 0) {
        return 0u;
    }
    _frame_flag = 0; /* 标记已读（数据仍可由 get_position 解析） */
    return 1u;
}

/* 从 _frame 提取第 field 个逗号字段（字段 0 = 帧 ID 之前段）：
 * 拷到 out（至多 max 字节）返回长度；越界/缺失返回 0。 */
static uint8_t _frame_field(uint8_t field, uint8_t *out, uint8_t max)
{
    uint8_t i, cur = 0, len = 0;

    for (i = 0; i < _frame_len; i++) {
        uint8_t ch = _frame[i];
        if (ch == ',') {
            if (cur == field) {
                return len;
            }
            cur++;
            len = 0;
        } else if (cur == field) {
            if (len < max - 1u) {
                out[len++] = ch;
            }
        }
    }
    return (cur == field) ? len : 0u;
}

/* ddmm.mmmm（或 dddmm.mmmm）→ 十进制度：整数/100 取度、余数分、
 * 小数分母按位数（最多 4 位）。无 stdlib（零标准库）。 */
static float _ddmm_to_deg(const uint8_t *s, uint8_t len)
{
    uint16_t int_part = 0;
    uint16_t frac = 0;
    uint8_t frac_digits = 0;
    uint8_t after_dot = 0;
    uint8_t i, k;
    float div = 1.0f;
    float deg, min;

    for (i = 0; i < len; i++) {
        uint8_t ch = s[i];
        if (ch == '.') {
            after_dot = 1;
            continue;
        }
        if (ch < '0' || ch > '9') {
            break;
        }
        if (after_dot) {
            if (frac_digits < 4u) {
                frac = (uint16_t)(frac * 10u + (uint16_t)(ch - '0'));
                frac_digits++;
            }
        } else {
            int_part = (uint16_t)(int_part * 10u + (uint16_t)(ch - '0'));
        }
    }
    for (k = 0; k < frac_digits; k++) {
        div *= 10.0f;
    }
    deg = (float)(int_part / 100u);
    min = (float)(int_part % 100u) + (float)frac / div;
    return deg + min / 60.0f;
}

uint8_t neo_6m_get_position(float *lat, float *lon)
{
    uint8_t field[14];
    uint8_t len;

    if (_frame_len == 0) {
        return 1u; /* 未收到过完整帧（页面 isGetData 语义——数据可重复解析） */
    }
    len = _frame_field(2u, field, sizeof(field)); /* 字段 2：有效位 A/V */
    if (len == 0u || field[0] != 'A') {
        return 2u; /* 数据无效（页面 usefullBuffer[0]=='A' 判定） */
    }
    len = _frame_field(3u, field, sizeof(field)); /* 字段 3：纬度 ddmm.mmmm */
    if (len == 0u) {
        return 2u;
    }
    *lat = _ddmm_to_deg(field, len);
    len = _frame_field(4u, field, sizeof(field)); /* 字段 4：N/S */
    if (len == 0u) {
        return 2u;
    }
    if (field[0] == 'S') {
        *lat = -*lat; /* 南纬为负 */
    }
    len = _frame_field(5u, field, sizeof(field)); /* 字段 5：经度 dddmm.mmmm */
    if (len == 0u) {
        return 2u;
    }
    *lon = _ddmm_to_deg(field, len);
    len = _frame_field(6u, field, sizeof(field)); /* 字段 6：E/W */
    if (len == 0u) {
        return 2u;
    }
    if (field[0] == 'W') {
        *lon = -*lon; /* 西经为负 */
    }
    return 0u;
}

void neo_6m_clear(void)
{
    uint16_t i;
    for (i = 0; i < NEO_6M_RX_BUF_SIZE; i++) {
        _rx[i] = 0;
    }
    for (i = 0; i < NEO_6M_FRAME_BUF_SIZE; i++) {
        _frame[i] = 0;
    }
    _rx_len = 0;
    _frame_len = 0;
    _frame_flag = 0;
}
