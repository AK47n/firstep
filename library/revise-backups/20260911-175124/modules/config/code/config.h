#ifndef _config_h_
#define _config_h_

#include "stdint.h"
#include "pin_config.h"

// ============================================================
//  外设参数集中定义（引脚宏已并入母版 pin_config.h——ADR 0010 接线单源：
//  UWB_UART / ZIGBEE_UART / LED_* / BUZZER_* / DIP_* 均在其中；
//  本文件保留波特率与显示/滤波参数，既有消费方引用不变）
// ============================================================

// UWB 基站串口波特率（UART 实例 = pin_config.h 的 UWB_UART = UART_1）
#define UWB_BAUD            115200

// OLED 软件I2C (已在 ml_oled.h 中定义: PB8=SCL, PB9=SDA)

// Zigbee 无线串口波特率（UART 实例 = pin_config.h 的 ZIGBEE_UART = UART_3）
#define ZIGBEE_BAUD         115200

// ============================================================
//  通用时间参数 (ms)
// ============================================================

#define OLED_UPDATE_MS      80      // OLED 刷新间隔 (12.5Hz，体感流畅)
#define EVENT_SHOW_MS       800     // 事件提示在OLED上显示的时长

// ============================================================
//  滤波参数
// ============================================================

// 滑动平均滤波窗口大小
//  窗口越大越平滑但响应越慢
#define FILTER_WIN_SIZE     8       // 距离滤波窗口
#define FILTER_AZ_WIN_SIZE  5       // 方位角滤波窗口

// 增量钳位 — 单次采样最大允许变化量，超过则钳位 (防止野值)
#define DIST_MAX_STEP       30      // 距离单步最大变化 (cm)
#define AZ_MAX_STEP         15      // 方位角单步最大变化 (度)

#endif
