#ifndef _config_h_
#define _config_h_

#include "stdint.h"

// ============================================================
//  引脚映射 — 所有硬件引脚集中定义，方便改线
// ============================================================

// UWB 基站串口：UART1 (PA9=TX → 基站RX, PA10=RX ← 基站TX)
#define UWB_UART            UART_1
#define UWB_BAUD            115200

// OLED 软件I2C (已在 ml_oled.h 中定义: PB8=SCL, PB9=SDA)

// 三个独立LED (共阴，高电平点亮)
#define LED_PORT           GPIO_C
#define LED_RED_PIN         Pin_13   // 红灯 — 关锁状态
#define LED_YELLOW_PIN      Pin_14   // 黄灯 — 迎宾区
#define LED_GREEN_PIN       Pin_15   // 绿灯 — 开锁状态

// 蜂鸣器 (有源蜂鸣器，低电平触发)
#define BUZZER_GPIO         GPIO_B
#define BUZZER_PIN          Pin_0

// DIP-4 拨码开关 (4位二进制ID，上拉输入，拨到ON=低电平)
#define DIP_GPIO            GPIO_B
#define DIP_PIN0            Pin_12
#define DIP_PIN1            Pin_13
#define DIP_PIN2            Pin_14
#define DIP_PIN3            Pin_15

// ============================================================
//  区域判定参数 — 现场用串口发送命令动态调整更方便
//     比赛时可根据实测微调
// ============================================================

// 开锁区阈值 (cm)
#define THR_UNLOCK_ENTER    130     // 进入开锁区: distance <= 130cm
#define THR_UNLOCK_EXIT     140     // 离开开锁区: distance > 140cm (滞回10cm)

// 迎宾区阈值 (cm)
#define THR_WELCOME_ENTER   230     // 进入迎宾区: distance <= 230cm
#define THR_WELCOME_EXIT    240     // 离开迎宾区: distance > 240cm (滞回10cm)

// 最大感应距离 (cm) — 超出此范围视为无钥匙
#define THR_SENSING_MAX     430

// TagID 掩码 — DIP-4 拨码只有4位，只比较低4位
#define TAGID_MASK          0x0F

// FOV 半角 (度) — 智能门锁正前方±45°范围
#define FOV_HALF_ANGLE      45

// Zigbee DL-20 无线串口：USART3 (PB10=TX → DL-20 RX, PB11=RX ← DL-20 TX)
#define ZIGBEE_UART         UART_3
#define ZIGBEE_BAUD         115200

// Zigbee 钥匙ID 超时 (ms) — 10Hz发送，丢5帧≈500ms → 认为钥匙离开
#define ZIGBEE_TIMEOUT_MS   500

// ============================================================
//  时间参数 (ms)
// ============================================================

#define OLED_UPDATE_MS      80      // OLED 刷新间隔 (12.5Hz，体感流畅)
#define TAG_TIMEOUT_MS      3000    // 超过3秒没收到数据 → 认为钥匙离开
#define EVENT_SHOW_MS       800     // 事件提示在OLED上显示的时长

// ============================================================
//  滤波参数
// ============================================================

// 滑动平均滤波窗口大小
//  窗口越大越平滑但响应越慢
//  要求4/5: 边界判定误差 ≤0.2m
#define FILTER_WIN_SIZE     8       // 距离滤波窗口 (增大以抑制抖动)
#define FILTER_AZ_WIN_SIZE  5       // 方位角滤波窗口 (增大以抑制抖动)

// 增量钳位 — 单次采样最大允许变化量，超过则钳位 (防止野值)
#define DIST_MAX_STEP       30      // 距离单步最大变化 (cm)
#define AZ_MAX_STEP         15      // 方位角单步最大变化 (度)

#endif
