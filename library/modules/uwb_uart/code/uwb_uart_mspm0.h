#ifndef _uwb_uart_mspm0_h_
#define _uwb_uart_mspm0_h_

#include "ti_msp_dl_config.h"
#include <stdint.h>

// ============================================================
//  UWB 基站定位数据帧 (0x2001)
//
//  帧格式 (37字节, 大端序):
//    [0-3]   Header       0xFFFFFFFF
//    [4-5]   PacketLength 0x0025 (37)
//    [6-7]   SequenceID   流水号
//    [8-9]   RequestCmd   0x2001
//    [10-11] VersionID    0x0102
//    [12-15] AnchorID     基站ID (uint32)
//    [16-19] TagID        标签ID = 设备身份 (uint32)
//    [20-23] Distance     径向距离 cm (uint32)
//    [24-25] Azimuth      方位角 度 (int16)
//    [26-27] Elevation    仰角 度 (int16)
//    [28-29] TagStatus    标签状态
//    [30-31] BatchSn      测距序号
//    [32-35] Reserve      预留
//    [36]    XorByte      XOR校验
//
//  总长 = 4(header) + 33(body) = 37 字节
//
//  接线：UWB_UART = UART2，PA23(TX) / PA24(RX)，115200 8N1（SysConfig）。
//  中断：UWB_UART_INST_IRQHandler 在本模块 .c 内定义，main.c 无需再定义。
// ============================================================

#define UWB_FRAME_SIZE      37
#define UWB_PAYLOAD_SIZE    33
#define UWB_BUF_SIZE        64

// 帧解析结果 (原始值)
typedef struct {
    uint32_t tag_id;
    uint32_t distance;      // cm
    int16_t  azimuth;       // 度
    int16_t  elevation;     // 度
    uint16_t seq_id;
} UWB_Data;

// 全局变量
extern volatile UWB_Data g_uwb_raw;         // 最新一帧原始数据
extern volatile UWB_Data g_uwb_filtered;    // 滤波后的数据 (区域判定用这个)
extern volatile uint8_t  g_uwb_updated;
extern volatile uint32_t g_uwb_last_tick;   // mspm0 记有效帧序号（无全局 systick；
                                            // 毫秒超时请同选 ntb_time 用
                                            // get_time_stamp_ms）
extern volatile uint32_t g_uwb_frame_count; // 累计收到有效帧数

// 函数
void uwb_uart_init(void);          // SYSCFG_DL_init() 后调用：开 UWB_UART NVIC
void uwb_rx_handler(void);         // 由 UWB_UART_INST_IRQHandler 调用
void uwb_filter_reset(void);       // 重置滤波器 (ID变更时调用)
uint32_t uwb_get_frame_rate(void); // 累计有效帧数（帧/秒估算由骨架按时间窗算）

#endif
