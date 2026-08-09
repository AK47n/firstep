#ifndef HUIDU_H
#define HUIDU_H


#include "ti_msp_dl_config.h"

// 接线
// 灰度模块 (8路) — 从左到右：PA26 PA25 PA24 PA23 PA22 PA21 PB9 PB8
// VCC       5V(根据说明书确定具体是多少电压，不能接错了)
// GND       GND
// L4       PA26
// L3       PA25
// L2       PA24
// L1       PA23
// R1       PA22
// R2       PA21
// R3       PB9
// R4       PB8

// 灰度值：huidu_value[i]==1 表示检测到黑线（索引 0~7 对应 L3 L2 L1 R1 R2 L4 R3 R4，
// 与 get_gpio_state 的读取顺序一致）
extern uint8_t huidu_value[8];

void huidu_get_value();

#endif
