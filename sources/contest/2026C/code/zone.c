#include "headfile.h"
#include "zone.h"
#include "config.h"

const char* zone_name(Zone_t z)
{
    switch (z)
    {
        case ZONE_NONE:    return "NONE";
        case ZONE_SENSING: return "SENSING";
        case ZONE_WELCOME: return "WELCOME";
        case ZONE_UNLOCK:  return "UNLOCK";
        default:           return "????";
    }
}

Zone_t zone_determine(Zone_t current, uint32_t distance, int16_t azimuth)
{
    // 1) FOV 检查：方位角(绝对值，夹角)必须在 0~45° 范围内
    if (azimuth > FOV_HALF_ANGLE)
        return ZONE_NONE;

    // 2) 超出最大感应距离
    if (distance > THR_SENSING_MAX)
        return ZONE_NONE;

    // 3) 带滞回的区域判定
    //    进入阈值比退出阈值更宽松，防止边界抖动
    switch (current)
    {
        case ZONE_UNLOCK:
            // 离开开锁区：distance > 进入阈值+滞回
            if (distance > THR_UNLOCK_EXIT)
            {
                if (distance <= THR_WELCOME_ENTER)
                    return ZONE_WELCOME;
                else
                    return ZONE_SENSING;
            }
            return ZONE_UNLOCK;

        case ZONE_WELCOME:
            if (distance <= THR_UNLOCK_ENTER)
                return ZONE_UNLOCK;
            if (distance > THR_WELCOME_EXIT)
                return ZONE_SENSING;
            return ZONE_WELCOME;

        case ZONE_SENSING:
            if (distance <= THR_UNLOCK_ENTER)
                return ZONE_UNLOCK;
            if (distance <= THR_WELCOME_ENTER)
                return ZONE_WELCOME;
            return ZONE_SENSING;

        case ZONE_NONE:
        default:
            // 首次进入（或从超时恢复），用进入阈值
            if (distance <= THR_UNLOCK_ENTER)
                return ZONE_UNLOCK;
            if (distance <= THR_WELCOME_ENTER)
                return ZONE_WELCOME;
            return ZONE_SENSING;
    }
}
