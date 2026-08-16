#ifndef _config_mspm0_h_
#define _config_mspm0_h_

/* ============================================================
 * 外设参数集中定义（mspm0 版）
 *
 * mspm0 的引脚 / UART 实例 / 波特率由母版 mspm0.syscfg 单源
 * （SysConfig 生成 ti_msp_dl_config.h），本头只保留与 stm32
 * config.h 同值的协议 / 显示 / 滤波参数——UWB / Zigbee 等
 * 协议驱动跨平台消费同一组宏。
 * ============================================================ */

// UWB 基站串口波特率（实例 = UWB_UART = UART2，SysConfig 已配 115200）
#define UWB_BAUD            115200

// Zigbee 无线串口波特率（实例 = ZIGBEE_UART = UART3，SysConfig 已配 115200）
#define ZIGBEE_BAUD         115200

// ============================================================
//  通用时间参数 (ms)
// ============================================================

#define OLED_UPDATE_MS      80      // OLED 刷新间隔 (12.5Hz，体感流畅)
#define EVENT_SHOW_MS       800     // 事件提示在OLED上显示的时长

// ============================================================
//  滤波参数（与 stm32 config.h 同值）
// ============================================================

// 滑动平均滤波窗口大小
//  窗口越大越平滑但响应越慢
#define FILTER_WIN_SIZE     8       // 距离滤波窗口
#define FILTER_AZ_WIN_SIZE  5       // 方位角滤波窗口

// 增量钳位 — 单次采样最大允许变化量，超过则钳位 (防止野值)
#define DIST_MAX_STEP       30      // 距离单步最大变化 (cm)
#define AZ_MAX_STEP         15      // 方位角单步最大变化 (度)

#endif
