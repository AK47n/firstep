#ifndef MOTOR_SET_SPEED_h
#define MOTOR_SET_SPEED_h

#include "ti_msp_dl_config.h"
#include "motor_crc.h"


void Motor_Set_ClosedLoop(void);//设置电机进入闭环

void Motor_Set_Speeds(int16_t v0, int16_t v1, int16_t v2, int16_t v3);//设置电机速度

void Modbus_ParseFrame(uint8_t data);



#endif
