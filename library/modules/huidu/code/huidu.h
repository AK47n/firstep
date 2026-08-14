#ifndef HUIDU_H
#define HUIDU_H


#include "ti_msp_dl_config.h"

// 接线（与母版 syscfg HUIDU 实例一致）
// 灰度模块 (8路) — 从左到右：L4 L3 L2 L1 R1 R2 R3 R4
// VCC       5V(根据说明书确定具体是多少电压，不能接错了)
// GND       GND
// L4       PA25
// L3       PA24
// L2       PA23
// L1       PA22
// R1       PA26
// R2       PA27
// R3       PB4   （地猛星 2×20 排针未引出，需扩展接线或改引脚）
// R4       PB5   （同上）

// 灰度值：huidu_value[i]==1 表示检测到黑线（索引 0~7 对应 L3 L2 L1 R1 R2 L4 R3 R4，
// 与 get_gpio_state 的读取顺序一致）
extern uint8_t huidu_value[8];

void huidu_get_value();

#endif
