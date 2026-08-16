#ifndef NTB_TIME_STM32_H
#define NTB_TIME_STM32_H

#include <stdint.h>

/* 系统毫秒时间戳（与 mspm0 侧 get_time_stamp_ms 同名同义）。 */
int64_t get_time_stamp_ms(void);

#endif // NTB_TIME_STM32_H
