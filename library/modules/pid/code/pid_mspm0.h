#ifndef __PID_MSPM0_h_
#define __PID_MSPM0_h_
#include "ti_msp_dl_config.h"
#include <stdint.h>

// OLED 大字格式化：将字符串填充为8字符（不足补空格，末尾加\0）
// 用于 OLED 大字模式，每行固定8字符（26H pid.h 同款，mspm0 侧随模块自带）
#define FMT8(buf, str) do { \
    int _i; \
    for (_i = 0; _i < 8 && (str)[_i]; _i++) (buf)[_i] = (str)[_i]; \
    for (; _i < 8; _i++) (buf)[_i] = ' '; \
    (buf)[8] = '\0'; \
} while(0)

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
void pid_control(void);
void pid_init(pid_t *pid, uint32_t mode, float p, float i, float d);
void motor_target_set(float spe1, float spe2);
void pidout_limit(pid_t *pid);

extern pid_t motorA;
extern pid_t motorB;
extern pid_t angle;
extern pid_t line_pid;

// ===== 小车全局状态 =====
extern int car_started;            // main 置1后小车开始运行
extern int motor_test_mode;        // 电机测试模式标志

extern char oled_line1[32];
extern char oled_line2[32];
extern char oled_line3[32];
extern char oled_line4[32];
extern volatile int oled_dirty;
#endif
