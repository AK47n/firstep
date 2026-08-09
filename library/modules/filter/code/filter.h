#ifndef _filter_h_
#define _filter_h_

#include "headfile.h"

// ============================================================
//  滑动平均滤波器
//  用于平滑 UWB 距离和方位角数据，减少抖动
//  提升区域边界判定的稳定性（要求3/4/5的精度需求）
// ============================================================

typedef struct {
    int32_t *buf;       // 环形缓冲区
    uint8_t  size;      // 窗口大小
    uint8_t  idx;       // 当前写入位置
    uint8_t  count;     // 已填充数量 (< size 时用实际count)
    int64_t  sum;       // 缓冲区元素之和 (快速更新，避免每次全量求和)
} SlidingFilter;

// 初始化
//  buf: 外部提供的数组 (大小 = size)
void filter_init(SlidingFilter *f, int32_t *buf, uint8_t size);

// 加入新值，返回滤波后的值 (当前窗口平均值)
int32_t filter_add(SlidingFilter *f, int32_t val);

// 获取当前滤波值 (不添加新值)
int32_t filter_get(SlidingFilter *f);

// 重置滤波器
void filter_reset(SlidingFilter *f);

#endif
