#include "ntb_time_stm32.h"
#include "headfile.h"

/* 系统毫秒时间戳（stm32）：复用母版 SysTick 1ms 节拍（ml_systick）。
 * 首次调用自动 systick_init 并让 g_systick 递增；之后只读。
 * 注意：ml_delay 的 delay_us/delay_ms 是 SysTick 轮询实现，会临时停用
 * SysTick——delay 期间时间戳暂停；需要严格计时的骨架请用 tim_interrupt_ms_init
 * 调度 + 本时间戳只作毫秒级非严格计时。 */

static uint8_t g_ntb_started = 0;

int64_t get_time_stamp_ms(void)
{
    if (!g_ntb_started) {
        systick_init();
        g_ntb_started = 1;
    }
    return (int64_t)g_systick;
}
