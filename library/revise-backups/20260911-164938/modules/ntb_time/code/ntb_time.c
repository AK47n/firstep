#include "ntb_time.h"
#include <stdbool.h>
#include <stdint.h>

/* 回绕累加（工单 ntb-time-wrap/01）：NTB = TIMG7 16 位 Basic_Periodic，
 * 时钟 32MHz / 256 = 125kHz，period = 62499+1 = 62500 ticks = 500ms/周。
 * 计数器从 LOAD 向下数到 0 后 ZERO 中断回绕——本文件在中断里累加整周
 * 毫秒数，get_time_stamp_ms 再拼当前周内已走过的毫秒（LOAD - 当前计数值），
 * 时间戳不再 500ms 回绕、不再恒 0（旧实现读一个未启动的计数器 / 500）。
 */
static volatile int64_t g_ntb_ms = 0;
static bool g_ntb_started = false;

static void ntb_start_once(void)
{
    if (g_ntb_started)
    {
        return;
    }
    NVIC_EnableIRQ(NTB_INST_INT_IRQN);
    DL_Timer_startCounter(NTB_INST);
    g_ntb_started = true;
}

void NTB_INST_IRQHandler(void)
{
    switch (DL_Timer_getPendingInterrupt(NTB_INST))
    {
    case DL_TIMER_IIDX_ZERO:
        g_ntb_ms += 500;
        break;
    default:
        break;
    }
}

int64_t get_time_stamp_ms()
{
    ntb_start_once();
    uint32_t remaining = DL_Timer_getTimerCount(NTB_INST);
    uint32_t elapsed_in_period = NTB_INST_LOAD_VALUE - remaining;
    return g_ntb_ms + (int64_t)elapsed_in_period * 500
           / ((int64_t)NTB_INST_LOAD_VALUE + 1);
}
