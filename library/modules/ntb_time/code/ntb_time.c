#include "ntb_time.h"

int64_t get_time_stamp_ms()
{
    int64_t counter_ = DL_Timer_getTimerCount(NTB_INST);
    return counter_ / 500;
}

