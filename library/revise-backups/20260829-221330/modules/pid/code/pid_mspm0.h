#ifndef __PID_MSPM0_h_
#define __PID_MSPM0_h_
#include "ti_msp_dl_config.h"
#include <stdint.h>

enum
{
  POSITION_PID = 0,  // 位置式
  DELTA_PID,         // 增量式
};

typedef struct
{
	float target;
	float now;
	float error[3];
	float p,i,d;
	float pout, dout, iout;
	float out;

	uint32_t pid_mode;

}pid_t;

void pid_cal(pid_t *pid);
void pid_init(pid_t *pid, uint32_t mode, float p, float i, float d);
void motor_target_set(float spe1, float spe2);
void pidout_limit(pid_t *pid);
void line_pid_track(void);  // PD 巡线输出：灰度偏差 → 左右轮目标速度

extern pid_t motorA;
extern pid_t motorB;
extern pid_t angle;
extern pid_t line_pid;
#endif
