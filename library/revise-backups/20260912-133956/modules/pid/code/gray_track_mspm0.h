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

void gray_init(void);
float line_error_calc(void);
unsigned char digtal(unsigned char channel);
unsigned char all_white_detect(void);

#endif
