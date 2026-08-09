#include "headfile.h"
#include "uwb_uart.h"
#include "filter.h"
#include "config.h"

// ============================================================
//  全局变量
// ============================================================
volatile UWB_Data g_uwb_raw        = {0};
volatile UWB_Data g_uwb_filtered   = {0};
volatile uint8_t  g_uwb_updated    = 0;
volatile uint32_t g_uwb_last_tick  = 0;
volatile uint32_t g_uwb_frame_count = 0;

// ============================================================
//  滑动平均滤波器 (距离 + 方位角分别滤波)
// ============================================================
static int32_t  dist_buf[FILTER_WIN_SIZE];
static int32_t  az_buf[FILTER_AZ_WIN_SIZE];
static SlidingFilter dist_filter;
static SlidingFilter az_filter;

// ============================================================
//  帧缓冲区 — union 叠加直接映射
// ============================================================
static union {
    uint8_t  raw[UWB_FRAME_SIZE];
    struct {
        uint32_t header;        // [0-3]
        uint16_t pkt_len;       // [4-5]
        uint16_t seq_id;        // [6-7]
        uint16_t cmd;           // [8-9]
        uint16_t version;       // [10-11]
        uint32_t anchor_id;     // [12-15]
        uint32_t tag_id;        // [16-19]
        uint32_t distance;      // [20-23]
        int16_t  azimuth;       // [24-25]
        int16_t  elevation;     // [26-27]
        uint16_t tag_status;    // [28-29]
        uint16_t batch_sn;      // [30-31]
        uint32_t reserve;       // [32-35]
        uint8_t  xor_byte;      // [36]
    } frame;
} uwb_buf;

static volatile uint8_t  uwb_idx    = 0;
static volatile uint8_t  uwb_synced = 0;

// ============================================================
//  大小端转换
// ============================================================
static inline uint16_t swap16(uint16_t x) {
    return (x >> 8) | (x << 8);
}

static inline uint32_t swap32(uint32_t x) {
    return ((x >> 24) & 0xFF)
         | ((x >>  8) & 0xFF00)
         | ((x <<  8) & 0xFF0000)
         | ((x << 24) & 0xFF000000);
}

// ============================================================
//  XOR 校验
// ============================================================
static uint8_t calc_xor(void)
{
    uint8_t x = 0;
    for (int i = 0; i < UWB_FRAME_SIZE; i++)
        x ^= uwb_buf.raw[i];
    return x;
}

// ============================================================
//  初始化
// ============================================================
void uwb_uart_init(void)
{
    uart_init(UWB_UART, UWB_BAUD, 0x01);
    uwb_idx    = 0;
    uwb_synced = 0;

    // 初始化滤波器
    filter_init(&dist_filter, dist_buf, FILTER_WIN_SIZE);
    filter_init(&az_filter,   az_buf,   FILTER_AZ_WIN_SIZE);
}

// ============================================================
//  帧解析 → 填充原始数据 → 滤波 → 填充滤波数据
// ============================================================
static void parse_frame(void)
{
    uint32_t header = swap32(uwb_buf.frame.header);
    if (header != 0xFFFFFFFF) return;

    uint16_t cmd = swap16(uwb_buf.frame.cmd);
    if (cmd != 0x2001) return;

    if (calc_xor() != 0) return;

    // ---- 填充原始数据 ----
    g_uwb_raw.tag_id    = swap32(uwb_buf.frame.tag_id);
    g_uwb_raw.distance  = swap32(uwb_buf.frame.distance);
    g_uwb_raw.azimuth   = (int16_t)swap16((uint16_t)uwb_buf.frame.azimuth);
    g_uwb_raw.elevation = (int16_t)swap16((uint16_t)uwb_buf.frame.elevation);
    g_uwb_raw.seq_id    = swap16(uwb_buf.frame.seq_id);

    // ---- 增量钳位：防止单次野值拉偏滤波窗口 ----
    // 距离钳位
    {
        int32_t cur_dist = (int32_t)g_uwb_filtered.distance;
        int32_t raw_dist = (int32_t)g_uwb_raw.distance;
        int32_t diff = raw_dist - cur_dist;
        if (cur_dist > 0)  // 滤波器已有有效值才钳位
        {
            if (diff > DIST_MAX_STEP)
                raw_dist = cur_dist + DIST_MAX_STEP;
            else if (diff < -DIST_MAX_STEP)
                raw_dist = cur_dist - DIST_MAX_STEP;
        }
        g_uwb_filtered.distance = (uint32_t)filter_add(&dist_filter, raw_dist);
    }

    // 方位角钳位
    {
        int16_t az_abs = (g_uwb_raw.azimuth < 0) ? -(int16_t)g_uwb_raw.azimuth : g_uwb_raw.azimuth;
        int16_t cur_az = g_uwb_filtered.azimuth;
        int16_t diff = az_abs - cur_az;
        if (cur_az > 0)  // 滤波器已有有效值才钳位
        {
            if (diff > AZ_MAX_STEP)
                az_abs = cur_az + AZ_MAX_STEP;
            else if (diff < -AZ_MAX_STEP)
                az_abs = cur_az - AZ_MAX_STEP;
        }
        g_uwb_filtered.azimuth = (int16_t)filter_add(&az_filter, (int32_t)az_abs);
    }

    // ---- 更新全局标志 ----
    g_uwb_updated  = 1;
    g_uwb_last_tick = g_systick;
    g_uwb_frame_count++;
}

// ============================================================
//  USART1 中断处理 — 字节级状态机
// ============================================================
void uwb_rx_handler(void)
{
    uint8_t byte = (uint8_t)(USART1->DR & 0xFF);

    // 检测帧头：连续 4 个 0xFF
    if (byte == 0xFF)
    {
        if (!uwb_synced)
        {
            uwb_buf.raw[uwb_idx++] = byte;
            if (uwb_idx >= 4)
            {
                uwb_synced = 1;
                // idx=4，接下来从第5字节开始收
            }
            return;
        }
        // 已同步则正常收
    }
    else
    {
        if (!uwb_synced)
        {
            uwb_idx = 0;
            return;
        }
    }

    // 写入缓冲
    if (uwb_idx < UWB_FRAME_SIZE)
        uwb_buf.raw[uwb_idx++] = byte;

    // 完整一帧
    if (uwb_idx >= UWB_FRAME_SIZE)
    {
        parse_frame();
        uwb_idx    = 0;
        uwb_synced = 0;
    }
}

// ============================================================
//  重置滤波器 (DIP ID 变更时调用，避免旧钥匙数据污染)
// ============================================================
void uwb_filter_reset(void)
{
    filter_reset(&dist_filter);
    filter_reset(&az_filter);
}

// ============================================================
//  获取帧率估算 (frame/s)
// ============================================================
uint32_t uwb_get_frame_rate(void)
{
    return g_uwb_frame_count;
}
