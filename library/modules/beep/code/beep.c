#include "beep.h"

/* 蜂鸣器驱动（MSPM0 占位实现）：地猛星排针已分配满，暂无蜂鸣器引脚。
 * 接线后按 stm32 侧 beep_stm32.c 同款实现（gpio 输出 + beep_beep 延时）。
 * 保留本模块是为了两平台 API 统一：beep_on/off 调用不因平台改写。 */

void beep_init(void)
{
    /* 未接蜂鸣器：占位，接线后初始化 GPIO 输出并 beep_off */
}

void beep_on(void)
{
    /* 未接蜂鸣器：占位 */
}

void beep_off(void)
{
    /* 未接蜂鸣器：占位 */
}

void beep_toggle(void)
{
    /* 未接蜂鸣器：占位 */
}

void beep_beep(uint16_t times, uint16_t on_ms, uint16_t off_ms)
{
    (void)times;
    (void)on_ms;
    (void)off_ms;
    /* 未接蜂鸣器：占位 */
}
