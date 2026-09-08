#ifndef _mpu6050_h
#define _mpu6050_h
#include "stdint.h"
#include "ml_i2c.h"
#include "math.h"

/* 使用前置（批 11 C 类核对）：MPU6050_Init **不初始化引脚/总线**——调用方须
 * 先调母版 I2C_Init()（ml_i2c，默认 PA11/PA12——见 pin_config.h 硬 I2C 段）；
 * 页面默认脚 SDA=PB8/SCL=PB9 未照抄（=母版 OLED 段，批次 2 已让位）。 */

#define MPU6050_ADDR	   0xd0 
#define SMPLRT_DIV       0x19
#define CONFIG           0x1a
#define GYRO_CONFIG      0x1b
#define ACCEL_CONFIG     0x1c
#define ACCEL_XOUT_H     0x3b
#define ACCEL_XOUT_L     0x3c
#define ACCEL_YOUT_H     0x3d
#define ACCEL_YOUT_L     0x3e
#define ACCEL_ZOUT_H     0x3f
#define ACCEL_ZOUT_L     0x40
#define TEMP_OUT_H       0x41 /* 温度高字节（MPU6050 寄存器表——原 0x65 为
                                 非定义寄存器（错误常量；0x65 无对应温度
                                 寄存器），本件温度路径未启用——订正保留
                                 （批 11 C 类核对修） */
#define TEMP_OUT_L       0x42
#define GYRO_XOUT_H      0x43
#define GYRO_XOUT_L      0x44
#define GYRO_YOUT_H      0x45
#define GYRO_YOUT_L      0x46
#define GYRO_ZOUT_H      0x47
#define GYRO_ZOUT_L      0x48
#define PWR_MGMT_1       0x6b
#define PWR_MGMT_2       0x6c
#define INT_ENABLE       0x38
#define WHO_AM_I         0x75

extern int16_t ax, ay, az, gx, gy, gz;
extern float roll_gyro, pitch_gyro, yaw_gyro;
extern float roll_acc, pitch_acc, yaw_acc;
extern float roll_Kalman, pitch_Kalman, yaw_Kalman;

void MPU6050_Write(uint8_t addr, uint8_t dat);
uint8_t MPU6050_Read(uint8_t addr);
void MPU6050_Init(void);
void MPU6050_GetData(void);

#endif

