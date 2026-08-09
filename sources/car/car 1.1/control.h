#ifndef	__CONTROL_H__
#define __CONTROL_H__

#include "ti_msp_dl_config.h"


void Control_AB(void);
void Control_ABCDA(void);
void Control_ACBDA(void);
void Control_ACBDAx4(void);
float PID_A(float Encoder,float Target);
float PID_B(float Encoder,float Target);
void set_Duty(uint8_t duty,uint8_t channel);
float PWM_Limit(float IN,float max,float min);
void Set_Pwm(int motor_left,int motor_right);
float xunji_centroid(float gain);
int myabs(int a);
float GYRO_Control(uint8_t now,float target);

#endif
