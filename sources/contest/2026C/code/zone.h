#ifndef _zone_h_
#define _zone_h_

#include "headfile.h"

// 区域枚举
typedef enum {
    ZONE_NONE = 0,      // 无钥匙 / 超FOV / 超时
    ZONE_SENSING,       // 感应区: distance > 迎宾区阈值
    ZONE_WELCOME,       // 迎宾区: 开锁区 < distance <= 迎宾区
    ZONE_UNLOCK         // 开锁区: distance <= 开锁区阈值
} Zone_t;

// 获取可读名称
const char* zone_name(Zone_t z);

// 区域判定 (带滞回)
//  current: 当前区域，用于滞回判断
//  distance: 径向距离 cm
//  azimuth:  方位角 α (0°~FOV_HALF_ANGLE, 已经取绝对值/滤波)
// 返回: 新区域
Zone_t zone_determine(Zone_t current, uint32_t distance, int16_t azimuth);

#endif
