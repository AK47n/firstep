#ifndef IMU_H
#define IMU_H

#include "ti_msp_dl_config.h"
#include <stdint.h>

// ===== 接线 =====
// MSPM0-IMU (新)  地猛星 MSPM0G3507
// VCC             5V
// GND             GND
// TX              PA31 (UART0 RX) — 已开启内部上拉，防浮空噪声
// RX              PA28 (UART0 TX)
//
// 通信：UART0 115200bps, 8N1, BUSCLK=40MHz
// 配置命令：AA 06 01 01 01 AD 00（CRC16 硬编码）
// 数据帧：  0A 03 04 [angle_H] [angle_L] [dps_H] [dps_L] [CRC_L] [CRC_H]
// 校验：    CRC16(Modbus)，对前 7 字节
// 噪声过滤：字节间隙检测 — 帧内字节间隙 >10ms → 丢弃部分帧（真帧 9 字节在 0.8ms 内连续到达）

// ===== 数据结构（兼容旧代码） =====
typedef struct {
    float yaw;     // Yaw角度 (°), 实际值 = gyro_angle_raw × 0.1
    float pitch;   // 保留（新IMU不支持，始终为 0）
    float roll;    // 保留（新IMU不支持，始终为 0）
} Attitude_t;

extern Attitude_t current_attitude;   // 姿态数据（中断更新）

// ===== 原始数据（中断更新） =====
extern volatile uint8_t  gyro_rx_done;       // 帧接收完成标志（用户读取后手动清零）
extern volatile int16_t  gyro_angle_raw;     // Yaw角度 raw (实际角度 = raw × 0.1°)
extern volatile int16_t  gyro_dps_raw;       // 角速度 raw (实际角速度 = raw × 0.1°/s)
extern volatile uint16_t gyro_frame_timeout; // 间隙计时器（10ms 定时器 ISR 递增，收到字节时清零）

// ===== API =====
void IMU_Init(void);                          // 初始化：清空FIFO + 使能UART接收中断
void IMU_ConfigReportRate(void);              // 发送配置命令（单次）
void IMU_ConfigReportRateBurst(uint8_t count, uint32_t interval_ms); // 连续发送 n 次配置命令
void IMU_FlushRX(void);                       // 清空 UART RX FIFO 中的残留字节
void IMU_ResetParser(void);                   // 手动重置解析状态机（重试前调用）
void IMU_ParseFrame(uint8_t data);            // 逐字节解析帧（ISR调用）

#endif
