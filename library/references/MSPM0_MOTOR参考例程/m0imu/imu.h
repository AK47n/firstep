#ifndef IMU_h
#define IMU_h

#include "ti_msp_dl_config.h"
#include "stdio.h"
#include "motor_crc.h"
void Gyro_ParseFrame(uint8_t data);

void Gyro_ConfigReportRateRx(void);//AA 06 01 01 01 AD 00


#endif
