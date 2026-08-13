#ifndef	__BOARD_H__
#define __BOARD_H__

#include "ti_msp_dl_config.h"
#include "inv_mpu.h"
#include "inv_mpu_dmp_motion_driver.h"
#include "dmpKey.h"
#include "dmpmap.h"
#include "mpu6050.h"
#include "IOI2C.h"
#include "filter.h"
#include "string.h"
#include "math.h"
#define ABS(a)      (a>0 ? a:(-a))
extern int32_t Get_Encoder_countA,Get_Encoder_countB;


void delay_us(unsigned long __us);
void delay_ms(unsigned long ms);
void delay_1us(unsigned long __us);
void delay_1ms(unsigned long ms);

void uart0_send_char(char ch);
void uart0_send_string(char* str);


#endif
