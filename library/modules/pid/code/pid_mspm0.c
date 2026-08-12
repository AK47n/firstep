#include "pid_mspm0.h"
#include "motor.h"
#include "gray_track_mspm0.h"
#include <math.h>

// ===== 集中宏定义区（可调参数）=====

// --- 电机左右轮速度校准 ---
#define MOTOR_A_SCALE     1.40f           // 左轮速度缩放（>1=补偿弱侧）
#define MOTOR_B_SCALE     0.70f           // 右轮速度缩放（>1=补偿弱侧）

// --- 速度闭环参数 ---
#define BASE_SPEED        15.0f           // 基础速度（编码器计数/10ms）
#define MAX_DUTY          1300            // mspm0 PWM 占空比上限（motor 模块 limit_duty 同值）

// --- 启动斜坡 ---
#define RAMP_CYCLES  50                   // 50周期x10ms=500ms完成加速

// --- PD 巡线参数 ---
#define LINE_DEADBAND    0.5f             // 死区阈值（越大越不敏感）
#define LINE_PID_OUT_MAX 6.0f             // 轮速差上限

// ===== PID 结构体 =====
pid_t motorA;
pid_t motorB;
pid_t angle;
pid_t line_pid;

// ===== 启动斜坡计数器 =====
static int ramp_cnt = 0;

// ===== PD巡线：上一次偏差（丢线保持用）=====
static float last_error = 0.0f;

// ==================== PID 初始化 ====================

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


// ==================== 电机目标速度设置（含左右轮校准） ====================
// mspm0 motor 模块接口：motor_set_direction(id, dir) 0停 1正转 2反转；
// 26H stm32 语义 motorA_dir 0=正转 1=反转 → 映射为 1/2。
void motor_target_set(float spe1, float spe2)
{
    if (spe1 >= 0) {
        motorA.target = spe1 * MOTOR_A_SCALE;
        motor_set_direction(1, 1);        // 正转
    } else {
        motorA.target = -spe1 * MOTOR_A_SCALE;
        motor_set_direction(1, 2);        // 反转
    }

    if (spe2 >= 0) {
        motorB.target = spe2 * MOTOR_B_SCALE;
        motor_set_direction(2, 1);        // 正转
    } else {
        motorB.target = -spe2 * MOTOR_B_SCALE;
        motor_set_direction(2, 2);        // 反转
    }
}


// ==================== PD巡线 ====================
// 边缘中点偏差 + 死区 + PD（无EMA滤波）
// EMA 已移除：EMA低通滤波与D项矛盾——EMA抹平变化→D项失效→反而加剧振荡。
// 陀螺角速度前馈阻尼（GYRO_DAMP_GAIN=0 已关闭，需求时骨架自加）已随决策层
// 剥离移除——外设依赖收敛，deps 不引 imu_uart。

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

    // 启动斜坡：目标速度从0平滑过渡到BASE_SPEED
    if (ramp_cnt < RAMP_CYCLES) {
        ramp_cnt++;
        float ramp = (float)ramp_cnt / (float)RAMP_CYCLES;
        base *= ramp;
    }

    // out>0 → 左轮加速右轮减速 → 右转回中
    motor_target_set(base + line_pid.out,
                     base - line_pid.out);
}


// ==================== PID 计算 ====================

void pid_cal(pid_t *pid)
{
    // 计算当前偏差
    pid->error[0] = pid->target - pid->now;

    // PID计算
    if (pid->pid_mode == DELTA_PID) {  // 增量式
        pid->pout = pid->p * (pid->error[0] - pid->error[1]);
        pid->iout = pid->i * pid->error[0];
        pid->dout = pid->d * (pid->error[0] - 2 * pid->error[1] + pid->error[2]);
        pid->out += pid->pout + pid->iout + pid->dout;
    } else if (pid->pid_mode == POSITION_PID) {  // 位置式
        pid->pout = pid->p * pid->error[0];
        pid->iout += pid->i * pid->error[0];
        pid->dout = pid->d * (pid->error[0] - pid->error[1]);
        pid->out = pid->pout + pid->iout + pid->dout;
    }

    // 记录前两次偏差
    pid->error[2] = pid->error[1];
    pid->error[1] = pid->error[0];
}


// ==================== PID 输出限幅 ====================

void pidout_limit(pid_t *pid)
{
    if (pid->out >= MAX_DUTY) pid->out = MAX_DUTY;
    if (pid->out <= 0)        pid->out = 0;
}
