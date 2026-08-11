#ifndef __gray_track_mspm0_h_
#define __gray_track_mspm0_h_
#include "ti_msp_dl_config.h"
#include <stdint.h>

#define D1 digtal(1)
#define D2 digtal(2)
#define D3 digtal(3)
#define D4 digtal(4)
#define D5 digtal(5)
#define D6 digtal(6)
#define D7 digtal(7)
#define D8 digtal(8)

// 速度系数：改这一个数就能整体调速（0.0~1.0，越小越慢）
#define SPEED_FACTOR 0.04f  // 降速减少摆动（原0.06→0.04）

void gray_init(void);
void track(void);
float line_error_calc(void);
unsigned char digtal(unsigned char channel);
unsigned char cross_detect(void);
unsigned char t_cross_detect(void);
unsigned char ret_t_cross_detect(void);
unsigned char all_white_detect(void);
unsigned char parking_block_detect(void);
unsigned char start_line_detect(void);  // 启停线检测：≥4路黑 → A点

#endif
