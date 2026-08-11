#include "pid_mspm0.h"
#include "motor.h"
#include "gray_track_mspm0.h"
#include "ball_detect.h"
#include <stdio.h>
#include <math.h>

// 陀螺角速度 raw（imu_uart 模块中断更新；符号级 extern 引用，motor 模块对
// key.c counter 同款先例——依赖按 notes 手动同选 imu_uart，不引入头文件）
extern volatile int16_t gyro_dps_raw;

// ===== 集中宏定义区（H题可调参数）=====

// --- 电机左右轮速度校准 ---
#define MOTOR_A_SCALE     1.40f           // 左轮速度缩放（>1=补偿弱侧）
#define MOTOR_B_SCALE     0.70f           // 右轮速度缩放（>1=补偿弱侧）

// --- 速度闭环参数 ---
#define BASE_SPEED        15.0f           // 基础速度（编码器计数/10ms）
#define MAX_DUTY          1300            // mspm0 PWM 占空比上限（motor 模块 limit_duty 同值）

// --- 启动斜坡 ---
#define RAMP_CYCLES  50                   // 50周期x10ms=500ms完成加速

// --- PD 巡线参数 ---
#define GYRO_DAMP_GAIN   0                // 陀螺前馈增益（0=关闭，0.03~0.10推荐）
#define LINE_DEADBAND    0.5f             // 死区阈值（越大越不敏感）
#define LINE_PID_OUT_MAX 6.0f             // 轮速差上限

// ===== PID 结构体 =====
pid_t motorA;
pid_t motorB;
pid_t angle;
pid_t line_pid;

// ===== OLED 调试缓冲区（ISR 只写内存，主循环负责刷 I2C）=====
char oled_line1[32] = "";
char oled_line2[32] = "";
char oled_line3[32] = "";
char oled_line4[32] = "";
volatile int oled_dirty = 0;

// ===== 小车全局状态 =====
int car_started     = 0;  // main 置1后启动巡线
int motor_test_mode = 0;  // 电机测试模式：1=跳过pid_control

// ===== 编码器计数（key 模块 GROUP1_IRQHandler 中断累加，本模块只读清零）=====
extern uint32_t counter_1_A;
extern uint32_t counter_2_A;

// ===== 启动斜坡计数器 =====
static int ramp_cnt = 0;

// ===== PD巡线：上一次偏差（丢线保持用）=====
static float last_error = 0.0f;

// ===== H题：运行计时 =====
static uint32_t run_time_s = 0;   // 累计运行秒数
static int time_cnt = 0;          // 每10ms加1，满100→1秒

// ===== 第2问：一圈巡线 + 启停线停车状态机 =====
enum {
    LAP_IDLE,            // 等待按键启动
    LAP_LEAVING_START,   // 刚启动，正在离开起点启停线（忽略初始≥4路黑）
    LAP_RUNNING,         // 正常运行中，等待检测启停线（完成一圈）
    LAP_STOPPING,        // 检测到启停线，减速停车中
    LAP_STOPPED,         // 已停车，显示总时间
};
static int lap_state = LAP_IDLE;

// 启停线消抖：连续检测到≥4路黑的帧数
#define STOP_LINE_DEBOUNCE    5     // 连续5帧×10ms=50ms确认（避免误触发）
#define STOP_ARM_COOLDOWN     150   // 离开起点后150帧×10ms=1.5s后才启用检测
static int stop_debounce_cnt = 0;   // 消抖计数
static int stop_arm_cooldown = 0;   // 启用检测前的冷却计数
static int leave_debounce = 0;      // 离开起点消抖（不在启停线上的连续帧数）


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
// 边缘中点偏差 + 陀螺角速度前馈 + 死区 + PD（无EMA滤波）
// EMA 已移除：EMA低通滤波与D项矛盾——EMA抹平变化→D项失效→反而加剧振荡

static void line_pid_track(void)
{
    float error = line_error_calc();

    // 丢线保持：全白时沿用上次偏差（按原方向继续回线）
    if (!all_white_detect())
        last_error = error;

    // 死区：微小偏差视为居中，防止中心附近来回微调
    float error_out = last_error;
    if (error_out > -LINE_DEADBAND && error_out < LINE_DEADBAND)
        error_out = 0.0f;

    // 陀螺仪角速度前馈阻尼
    // gyro_dps_raw×0.1 = 偏航角速度(°/s)（mspm0 imu 模块语义；26H 用 gz/16.4）
    // 正值=车身右转 → now加正偏置 → PID输出左转力 → 抵消右转惯性
    float gyro_rate = (float)gyro_dps_raw * 0.1f;
    float gyro_damp = gyro_rate * GYRO_DAMP_GAIN;

    line_pid.target = 0.0f;
    line_pid.now = -error_out + gyro_damp;  // 取反偏差 + 陀螺前馈
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


// ==================== 主控制函数（MOTOR_PID_INST 10ms 中断调用） ====================
// 26H stm32 侧由 TIM3_IRQHandler 每 10ms 调用；mspm0 侧需在 main.c 的
// MOTOR_PID_INST_IRQHandler（或自建 10ms 定时器中断）里调用：
//   1) 读编码器：counter_1_A/counter_2_A（key 模块中断累加）→ 清零 → 入 now
//   2) pid_control()

void pid_control()
{
    int dutyA = 0, dutyB = 0;

    // ===== 电机测试模式：不做任何控制 =====
    if (motor_test_mode)
        return;

    // ===== 解析 K230 钢珠检测数据（每10ms消费UART缓冲区）=====
    ball_detect_parse();

    // ===== 第2问：一圈巡线+启停线停车状态机 =====

    // --- 离开起点消抖（LEAVING_START中判断是否已离开启停线）---
    if (lap_state == LAP_LEAVING_START) {
        if (!start_line_detect()) {
            leave_debounce++;
            if (leave_debounce >= 10) {  // 连续10帧(100ms)不在启停线上=已离开
                leave_debounce = 0;
                lap_state = LAP_RUNNING;
                stop_arm_cooldown = STOP_ARM_COOLDOWN;
                stop_debounce_cnt = 0;
            }
        } else {
            leave_debounce = 0;  // 还在启停线上，重置消抖
        }
    }

    // --- IDLE：停止所有电机 + 重置状态 ---
    if (lap_state == LAP_IDLE) {
        motor_set_duty(1, 0);
        motor_set_duty(2, 0);
        motorA.iout = 0.0f; motorA.out = 0.0f;
        motorA.error[0] = 0.0f; motorA.error[1] = 0.0f;
        motorB.iout = 0.0f; motorB.out = 0.0f;
        motorB.error[0] = 0.0f; motorB.error[1] = 0.0f;
        line_pid.out = 0.0f;
        line_pid.error[0] = 0.0f; line_pid.error[1] = 0.0f; line_pid.error[2] = 0.0f;
        ramp_cnt = 0;
        run_time_s = 0;
        time_cnt = 0;
        stop_debounce_cnt = 0;
        stop_arm_cooldown = STOP_ARM_COOLDOWN;
        leave_debounce = 0;
        // 等待按键
        if (car_started) {
            lap_state = LAP_LEAVING_START;
            ramp_cnt = 0;
        }
    }

    // --- STOPPED：电机停转，冻结显示 ---
    if (lap_state == LAP_STOPPED) {
        motor_set_duty(1, 0);
        motor_set_duty(2, 0);
    }

    // --- STOPPING：减速停车 ---
    if (lap_state == LAP_STOPPING) {
        motor_target_set(0, 0);
        pid_cal(&motorA);
        pid_cal(&motorB);
        dutyA = (int)motorA.out;
        dutyB = (int)motorB.out;
        if (dutyA < 0) dutyA = 0; if (dutyB < 0) dutyB = 0;
        if (dutyA > MAX_DUTY) dutyA = MAX_DUTY;
        if (dutyB > MAX_DUTY) dutyB = MAX_DUTY;
        motor_set_duty(1, dutyA);
        motor_set_duty(2, dutyB);
        // 速度降到0后进入STOPPED
        if (dutyA == 0 && dutyB == 0) {
            lap_state = LAP_STOPPED;
        }
    }

    // --- LEAVING_START / RUNNING：巡线 + 速度闭环（共享代码路径）---
    if (lap_state == LAP_LEAVING_START || lap_state == LAP_RUNNING) {
        line_pid_track();

        // RUNNING状态：冷却递减 + 检测启停线
        if (lap_state == LAP_RUNNING) {
            if (stop_arm_cooldown > 0)
                stop_arm_cooldown--;
            if (stop_arm_cooldown <= 0 && start_line_detect()) {
                stop_debounce_cnt++;
                if (stop_debounce_cnt >= STOP_LINE_DEBOUNCE) {
                    lap_state = LAP_STOPPING;
                    // 跳过本次速度输出，让STOPPING接管
                    goto oled_update;
                }
            } else {
                stop_debounce_cnt = 0;
            }
        }

        // 速度闭环输出
        pid_cal(&motorA);
        pid_cal(&motorB);
        dutyA = (int)motorA.out;
        dutyB = (int)motorB.out;
        if (dutyA > MAX_DUTY) { dutyA = MAX_DUTY; motorA.out = MAX_DUTY; motorA.iout = MAX_DUTY - motorA.pout - motorA.dout; }
        if (dutyA < 0)        { dutyA = 0;        motorA.out = 0;        motorA.iout = -motorA.pout - motorA.dout; }
        if (dutyB > MAX_DUTY) { dutyB = MAX_DUTY; motorB.out = MAX_DUTY; motorB.iout = MAX_DUTY - motorB.pout - motorB.dout; }
        if (dutyB < 0)        { dutyB = 0;        motorB.out = 0;        motorB.iout = -motorB.pout - motorB.dout; }
        motor_set_duty(1, dutyA);
        motor_set_duty(2, dutyB);
    }

oled_update:
    // ===== OLED调试显示：每200ms刷新 =====
    {
        static int dbg_cnt = 0;
        dbg_cnt++;
        if (dbg_cnt >= 20) {
            dbg_cnt = 0;
            char tmp[16];

            // 计时（LEAVING_START和RUNNING期间才计时）
            if (lap_state == LAP_LEAVING_START || lap_state == LAP_RUNNING) {
                time_cnt++;
                if (time_cnt >= 100) { time_cnt = 0; run_time_s++; }
            }

            switch (lap_state) {
            case LAP_IDLE:
                FMT8(oled_line1, "H: BALL");
                FMT8(oled_line2, "PressKey");
                break;
            case LAP_LEAVING_START:
                sprintf(tmp, "TIME:%2lus", (unsigned long)run_time_s);
                FMT8(oled_line1, tmp);
                FMT8(oled_line2, "Start...");
                break;
            case LAP_RUNNING:
                sprintf(tmp, "TIME:%2lus", (unsigned long)run_time_s);
                FMT8(oled_line1, tmp);
                FMT8(oled_line2, "Running.");
                break;
            case LAP_STOPPING:
                sprintf(tmp, "TIME:%2lus", (unsigned long)run_time_s);
                FMT8(oled_line1, tmp);
                FMT8(oled_line2, "Stoping.");
                break;
            case LAP_STOPPED:
                sprintf(tmp, "TIME:%2lus", (unsigned long)run_time_s);
                FMT8(oled_line1, tmp);
                FMT8(oled_line2, "ARRIVED");
                break;
            }

            oled_line3[0] = '\0';
            oled_line4[0] = '\0';
            oled_dirty = 1;
        }
    }
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
