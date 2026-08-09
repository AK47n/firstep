#ifndef __PID_h_
#define __PID_h_
#include "headfile.h"

// OLED 大字格式化：将字符串填充为8字符（不足补空格，末尾加\0）
// 用于 OLED_ShowStringBig() 大字模式，每行固定8字符
#define FMT8(buf, str) do { \
    int _i; \
    for (_i = 0; _i < 8 && (str)[_i]; _i++) (buf)[_i] = (str)[_i]; \
    for (; _i < 8; _i++) (buf)[_i] = ' '; \
    (buf)[8] = '\0'; \
} while(0)

enum
{
  POSITION_PID = 0,  // λ��ʽ
  DELTA_PID,         // ����ʽ
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
void set_turn_dir(int dir);

extern pid_t motorA;
extern pid_t motorB;
extern pid_t angle;
extern pid_t line_pid;
extern int cross_state;
extern int cross_cnt;
extern int turn_dir;

// ===== 小车全局状态 =====
extern int car_started;            // PB5按下后置1，小车开始运行
extern int motor_test_mode;        // 电机测试模式标志
extern int dest_index;             // 目的地编号（0=未锁定，1/2/3=药房号）
extern int cross_count;            // 已处理的十字路口计数
extern int route_complete;         // 路由表执行完毕，开始寻找药房
extern int return_mode;            // 1=返程模式（掉头后沿路径返回）
extern int all_return_done;        // 返程路口全部处理完，准备进起始区
extern int in_pharmacy;            // 已进入药房，停止
extern int pharmacy_state;         // 药房送达状态机状态

// ===== K230动态路口决策 =====
#define CROSS_ACTION_K230_DECIDE  3  // 需要K230动态决定左转/右转
extern int recognition_active;       // 识别窗口激活标志
extern int k230_turn_ready;          // K230决策已就绪
extern int k230_turn_result;         // 决策结果: CROSS_ACTION_LEFT 或 CROSS_ACTION_RIGHT

// ===== 远端导航（大T字路口 + 小T字路口）=====
extern int far_nav_active;           // 远端导航激活标志
extern int far_state;                // 远端导航状态机当前状态

// ===== 远端返程导航（小T + 大T路口返程）=====
extern int far_return_active;        // 远端返程激活标志
extern int far_return_state;         // 远端返程状态机当前状态

extern char oled_line1[32];
extern char oled_line2[32];
extern char oled_line3[32];
extern char oled_line4[32];
extern volatile int oled_dirty;
#endif
