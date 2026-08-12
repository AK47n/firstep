#include "headfile.h"
#include "pid.h"
#include "motor_stm32.h" // motor 模块的 code/motor.h 是 mspm0 版（含 ti_msp_dl_config.h），stm32 侧用独立头
#include "gray_track.h"
#include <math.h>
// ===== 集中宏定义区（所有可调参数集中于此，方便修改）=====

// --- 电机左右轮速度校准 ---
#define MOTOR_A_SCALE     1.40f           // 左轮速度缩放（>1=补偿弱侧）
#define MOTOR_B_SCALE     0.70f           // 右轮速度缩放（>1=补偿弱侧）

// --- 速度闭环参数 ---
#define BASE_SPEED        15.0f           // 基础速度（编码器计数/10ms）

// --- 启动斜坡 ---
#define RAMP_CYCLES  50                   // 50周期x10ms=500ms完成加速

// --- PD 巡线参数 ---
#define LINE_DEADBAND    0.5f             // 死区阈值
#define LINE_PID_OUT_MAX 6.0f             // 轮速差上限


pid_t motorA;
pid_t motorB;
pid_t angle;
pid_t line_pid;

// ===== 启动斜坡计数器 =====
static int ramp_cnt = 0;

// ===== 巡线偏差记忆（丢线保持用）=====
static float last_error = 0.0f;

void pid_init(pid_t *pid, uint32_t mode, float p, float i, float d)
{
	pid->pid_mode = mode;
	pid->p = p;
	pid->i = i;
	pid->d = d;
	// 清零PID状态，防止残留值导致飞车
	pid->target = 0;
	pid->now = 0;
	pid->error[0] = 0;
	pid->error[1] = 0;
	pid->error[2] = 0;
	pid->pout = 0;
	pid->iout = 0;
	pid->dout = 0;
	pid->out = 0;
}

// 左右轮速度校准：线偏右(56之间) → PID在右转纠偏 → 车天然左转 → 右轮偏强/左轮偏弱

void motor_target_set(float spe1, float spe2)
{
	if(spe1 >= 0)
	{
		motorA_dir = 0;        // 正转
		motorA.target = spe1 * MOTOR_A_SCALE;
	}
	else
	{
		motorA_dir = 1;        // 反转
		motorA.target = -spe1 * MOTOR_A_SCALE;
	}

	if(spe2 >= 0)
	{
		motorB_dir = 0;        // 正转
		motorB.target = spe2 * MOTOR_B_SCALE;
	}
	else
	{
		motorB_dir = 1;        // 反转
		motorB.target = -spe2 * MOTOR_B_SCALE;
	}
}

// ===== PD巡线：边缘中点偏差 + 死区 + PD（无EMA滤波） =====
// ★ EMA 已移除。EMA低通滤波与PD的D项（微分）互相矛盾：
//   EMA把误差变化"抹平"→D项看不到真实变化率→阻尼失效→反而加剧振荡。
//   现在传感器偏差直接进PD，D项能即时反应→真正抑制微摆。
// 陀螺角速度前馈阻尼（GYRO_DAMP_GAIN=0 已关闭，需求时骨架自加）已随
// 决策层剥离移除——外设依赖收敛，deps 不引姿态模块。
void line_pid_track(void)
{
    float error = line_error_calc();

    // 丢线保持：全白时沿用上次偏差（按原方向继续回线）
    if (!all_white_detect())
        last_error = error;

    // 死区：微小偏差视为居中，防止中心附近来回微调
    float error_out = last_error;
    if (error_out > -LINE_DEADBAND && error_out < LINE_DEADBAND)
        error_out = 0.0f;

    line_pid.target = 0.0f;
    line_pid.now = -error_out;  // 取反偏差
    pid_cal(&line_pid);  // POSITION_PID: out = P*偏差 + D*d(偏差)/dt

    // 输出限幅
    if (line_pid.out >  LINE_PID_OUT_MAX) line_pid.out =  LINE_PID_OUT_MAX;
    if (line_pid.out < -LINE_PID_OUT_MAX) line_pid.out = -LINE_PID_OUT_MAX;

    // 弯道减速：偏差越大基础速度越低
    float base = BASE_SPEED * (1.0f - 0.05f * fabs(last_error));

    // 启动斜坡
    if (ramp_cnt < RAMP_CYCLES)
    {
        ramp_cnt++;
        float ramp = (float)ramp_cnt / (float)RAMP_CYCLES;
        base *= ramp;
    }

    // out>0 → 左轮加速右轮减速 → 右转回中
    motor_target_set(base + line_pid.out,
                     base - line_pid.out);
}

void pid_cal(pid_t *pid)
{
	// 计算当前偏差
	pid->error[0] = pid->target - pid->now;

	// PID计算
	if(pid->pid_mode == DELTA_PID)  // 增量式
	{
		pid->pout = pid->p * (pid->error[0] - pid->error[1]);
		pid->iout = pid->i * pid->error[0];
		pid->dout = pid->d * (pid->error[0] - 2 * pid->error[1] + pid->error[2]);
		pid->out += pid->pout + pid->iout + pid->dout;
	}
	else if(pid->pid_mode == POSITION_PID)  // 位置式
	{
		pid->pout = pid->p * pid->error[0];
		pid->iout += pid->i * pid->error[0];
		pid->dout = pid->d * (pid->error[0] - pid->error[1]);
		pid->out = pid->pout + pid->iout + pid->dout;
	}

	// 记录前两次偏差
	pid->error[2] = pid->error[1];
	pid->error[1] = pid->error[0];

	// 输出限幅
//	if(pid->out>=MAX_DUTY)
//		pid->out=MAX_DUTY;
//	if(pid->out<=0)
//		pid->out=0;

}

void pidout_limit(pid_t *pid)
{
	// 输出限幅
	if(pid->out>=MAX_DUTY)
		pid->out=MAX_DUTY;
	if(pid->out<=0)
		pid->out=0;
}
