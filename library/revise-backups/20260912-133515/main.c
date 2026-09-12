/*
 * 巡线小车决策框架 —— 题型：line_follow（car 1.1 巡线模板 mspm0 提炼）
 *
 * 本文件是「题型确定性框架段」（参考条目 framework/main.c）：骨架生成时
 * 原样注入 main.c 生成 prompt，作为**必须保留的结构**。类型 = 通用巡线
 * 小车主循环：灰度传感器读线 → PID 差速控制 → 主循环调度（10ms 节拍）。
 * 平台 / 接口中立：所有硬件调用一律写成注释占位
 *   // TODO: <角色> 由接口块替换
 * 由 AI 按当前所选模块接口实现（接口块里真实存在的函数）。
 *
 * 框架约定（AI 必须遵守）：
 * 1. 枚举 / 调度循环 / 框架函数名保持原样，改动只出现在 TODO 位；
 * 2. 控制分层：每周期「读线 → 计算偏差 → 设置电机」三步，不做题外逻辑；
 * 3. 所有持续运行逻辑挂在 10ms 调度周期上（isr 每 10ms 调一次
 *    xunji_dispatch），单次调度内不阻塞；
 * 4. 安全兜底：任何状态转换都要有超时转移，不许死等；
 * 5. 不在框架里写死参数（速度 / 偏差增益 / 死区全部经 TODO 参数区注入）。
 */

#include "ti_msp_dl_config.h"
#include "delay.h"
#include "led.h"
#include "beep.h"
#include "led_beep.h"
#include "motor.h"
#include "pid_mspm0.h"
#include "gray_track_mspm0.h"
#include "imu.h"

// ===== 巡线状态机 =====
typedef enum {
    XUNJI_STOP,        /* 等待启动（按键 / 上电复位） */
    XUNJI_FOLLOW,      /* 正常巡线中 */
    XUNJI_WAIT_LINE    /* 等待特定线型（如停车区） */
} xunji_state_t;

static xunji_state_t xunji_state = XUNJI_STOP;

// ===== TODO 参数区（AI 按题面 / 实际底盘标定值填写）=====
#define XUNJI_TICK_MS          10U     /* 调度节拍：主循环 delay_ms 周期 */
#define START_DELAY_MS         1000U   /* 上电 / 复位后的启动等待（非阻塞计数） */
#define XUNJI_BASE_SPEED       15.0f   /* 基础速度（编码器计数/10ms 量纲，与 pid 模块一致） */
#define LINE_PID_KP            0.9f    /* 巡线 PD 参数（参考例程取值，需实车标定） */
#define LINE_PID_KI            0.0f
#define LINE_PID_KD            0.0f
#define LINE_DEADBAND          0.5f    /* 偏差死区：中心附近不做微调 */
#define LINE_PID_OUT_MAX       6.0f    /* 轮速差上限（限幅保护） */
#define POINT_BLACK_CHANNELS   4U      /* 判定“经过 A/B/C/D 点 / 停车特征”的黑通道数阈值 */
#define POINT_DEBOUNCE_FRAMES  5U      /* 连续 5 帧×10ms=50ms 确认，防误触发 */
#define POINT_ARM_FRAMES       150U    /* 起步后 1.5s 才允许顶点检测，防起点误判 */
#define WAIT_LINE_TIMEOUT_MS   800U    /* WAIT_LINE 最长停留（安全超时，不许死等） */

/* 电机速度内环（位置式 PID）：输入 = 编码器计数/10ms，输出 = PWM 占空比。
 * 目标值由 motor_target_set() 写入（motorA.target / motorB.target），
 * 增益需按实车（轮径 48mm、260 线）标定：先加 Kp 到能跟随且不振荡，再加少量 Ki 消静差。 */
#define MOTOR_PID_KP           5.0f
#define MOTOR_PID_KI           0.5f
#define MOTOR_PID_KD           0.0f

/* 两轮正方向标定电平：装载后若某轮前进方向相反，把对应宏改成另一个电平即可，
 * 不必改动巡线 / 内环逻辑。电机 1 = A 组（PWMA/AIN），电机 2 = B 组（PWMB/BIN）。 */
#define MOTOR1_DIR_FORWARD     1U
#define MOTOR2_DIR_FORWARD     1U

// ===== 连续运行期模块级状态（全部在 xunji_dispatch 内读写）=====
static float    line_last_error = 0.0f;  /* 丢线保持：上一帧有效偏差 */
static uint16_t startup_ms      = 0;     /* 上电启动等待计时 */
static uint16_t point_arm_cnt   = 0;     /* 起步冷却计数（帧） */
static uint8_t  point_debounce  = 0;     /* 顶点 / 停车特征消抖计数（帧） */
static uint16_t wait_line_ms    = 0;     /* WAIT_LINE 停留计时（安全超时） */

/*
 * 10ms 调度周期入口（isr 或定时器回调调用）。
 * 读线 → 算偏差 → 差速控制；状态机只做最小化转移。
 */
static void xunji_dispatch(void) {

    // TODO: 读按键（本接口块未提供按键模块；若后续接入，在此读取启动/停止键）
    // TODO: 读灰度线由各 case 内调用 line_error_calc() / digtal() 完成

    switch (xunji_state) {
        case XUNJI_STOP:
            // 上电 / 复位后的等待态：先保证静止，再按延时非阻塞启动
            if (startup_ms < START_DELAY_MS) {
                startup_ms += XUNJI_TICK_MS;
                motor_target_set(0.0f, 0.0f);   /* 等待期两轮目标速度为 0 */
            } else {
                // TODO: 启动键按下 → xunji_state = XUNJI_FOLLOW —— 由接口块替换
                led_beep_alarm(1, 60, 60);      /* 启动声光提示（阻塞约 120ms，仅状态入口调用） */
                startup_ms     = 0;
                point_arm_cnt  = 0;
                point_debounce = 0;
                xunji_state    = XUNJI_FOLLOW;
            }
            break;

        case XUNJI_FOLLOW:
        {
            float err;                          /* 灰度线位置偏差（加权质心） */
            float err_dead;                     /* 过死区后的偏差 */
            float base;                         /* 本周期基础速度 */
            unsigned char black_cnt = 0;        /* 本周期黑通道计数（顶点特征） */
            int32_t enc_l, enc_r;               /* 内环：本周期左右轮编码器脉冲（读后清零） */

            /* ---- 1) 读线：灰度偏差 ---- */
            err = line_error_calc();
            if (!all_white_detect()) {          /* 有线才更新；全白=丢线时沿用上次偏差 */
                line_last_error = err;
            }
            err_dead = line_last_error;
            if (err_dead > -LINE_DEADBAND && err_dead < LINE_DEADBAND) {
                err_dead = 0.0f;                /* 死区 */
            }

            /* ---- 2) 偏差 → 巡线 PD 输出 ---- */
            line_pid.target = 0.0f;
            line_pid.now    = -err_dead;        /* 取反：偏差为正 → 需右转回中 */
            pid_cal(&line_pid);
            pidout_limit(&line_pid);            /* 模块内限幅 */
            if (line_pid.out >  LINE_PID_OUT_MAX) line_pid.out =  LINE_PID_OUT_MAX;
            if (line_pid.out < -LINE_PID_OUT_MAX) line_pid.out = -LINE_PID_OUT_MAX;

            /* 弯道减速：偏差越大基础速度越低 */
            base = XUNJI_BASE_SPEED * (1.0f - 0.05f * (err_dead > 0.0f ? err_dead : -err_dead));
            if (base < 0.0f) base = 0.0f;

            /* ---- 3) 巡线控制：偏差 → 差速（左 = base+out，右 = base-out）---- */
            motor_target_set(base + line_pid.out, base - line_pid.out);

            /* ---- 4) 内环：编码器 → 速度 PID → PWM（电机 1 = 左轮，电机 2 = 右轮）---- */
            motor_encoder_read(&enc_l, &enc_r); /* 读脉冲并清零，量纲 = 计数/10ms */
            motorA.now = (float)enc_l;
            motorB.now = (float)enc_r;
            pid_cal(&motorA);
            pid_cal(&motorB);
            motor_set_duty(1, (uint32_t)limit_duty((int)motorA.out));
            motor_set_duty(2, (uint32_t)limit_duty((int)motorB.out));

            /* ---- 5) 顶点 / 停车特征检测（连续 N 帧 ≥ 阈值通道数为黑）---- */
            if (digtal(1)) black_cnt++;         /* D1 */
            if (digtal(2)) black_cnt++;         /* D2 */
            if (digtal(3)) black_cnt++;         /* D3 */
            if (digtal(4)) black_cnt++;         /* D4 */
            if (digtal(5)) black_cnt++;         /* D5 */
            if (digtal(6)) black_cnt++;         /* D6 */
            if (digtal(7)) black_cnt++;         /* D7 */
            if (digtal(8)) black_cnt++;         /* D8 */

            if (point_arm_cnt < POINT_ARM_FRAMES) {
                point_arm_cnt++;                /* 起步冷却：刚离开始点时不判顶点 */
            } else if (black_cnt >= POINT_BLACK_CHANNELS) {
                point_debounce++;
                if (point_debounce >= POINT_DEBOUNCE_FRAMES) {
                    point_debounce = 0;
                    // TODO: 检测到停车区特征（连续 N 帧）→ xunji_state = XUNJI_WAIT_LINE
                    led_beep_alarm(1, 50, 50);  /* 经过 A/B/C/D 点的声光提示 */
                    xunji_state = XUNJI_WAIT_LINE;
                }
            } else {
                point_debounce = 0;             /* 特征消失，消抖计数清零 */
            }

            /* TODO: 顶点判定若改用 IMU 偏航角 / 编码器里程，请在此替换黑通道计数法 */
            break;
        }

        case XUNJI_WAIT_LINE:
            // TODO: 停车：速度置零 / 等待确认
            motor_target_set(0.0f, 0.0f);       /* 两轮目标速度为 0（内环随之刹停） */

            if (wait_line_ms == 0U) {
                led_beep_alarm(2, 80, 80);      /* 停车声光提示（阻塞约 320ms，仅入口一次） */
            }

            // TODO: 确认完成（超时或按键）→ 回 XUNJI_FOLLOW / XUNJI_STOP
            if (wait_line_ms < WAIT_LINE_TIMEOUT_MS) {
                wait_line_ms += XUNJI_TICK_MS;  /* 超时兜底，不在状态内死等 */
            } else {
                wait_line_ms   = 0;
                startup_ms     = 0;
                point_arm_cnt  = 0;
                point_debounce = 0;
                xunji_state    = XUNJI_STOP;    /* 确认完成（超时）→ 回 XUNJI_STOP */
                /* TODO: 第(4)项 4 圈：此处改为 lap++，未满 4 圈回 XUNJI_FOLLOW */
            }
            break;
    }
}

/*
 * main() 骨架：初始化 → 调度循环（while(1) 内只调 xunji_dispatch）。
 */
int main(void) {
    /* ---- 系统时钟 / 引脚 / 外设（SysConfig 生成）---- */
    SYSCFG_DL_init();           /* SysConfig 外设初始化链：时钟 / 引脚 / UART0 / 定时器 */

    /* ---- 模块初始化：按依赖顺序 ---- */
    led_init(LED_RED);          /* LED 通道（LED_CHANNEL_COUNT=1，LED_RED=0） */
    beep_init();                /* 蜂鸣器 */
    led_beep_init();            /* 声光提示组合模块（LED + 蜂鸣器） */
    gray_init();                /* 灰度巡线传感器 */
    motor_init(1);              /* 电机 1 = A 组（PWMA/AIN）→ 左轮 */
    motor_init(2);              /* 电机 2 = B 组（PWMB/BIN）→ 右轮 */
    IMU_Init();                 /* IMU UART 接收中断 + 解析状态机 */
    IMU_FlushRX();              /* 清空残留字节，避免状态机错位 */
    IMU_ConfigReportRate();     /* 发送上报配置（单次）—— TODO: 未回帧时改用 IMU_ConfigReportRateBurst */

    /* 巡线 PD 参数注入（pid_mspm0.h 的 line_pid 实例） */
    pid_init(&line_pid, POSITION_PID, LINE_PID_KP, LINE_PID_KI, LINE_PID_KD);

    /* 电机速度内环参数注入：编码器脉冲计数/10ms → PWM 占空比（位置式 PID） */
    pid_init(&motorA, POSITION_PID, MOTOR_PID_KP, MOTOR_PID_KI, MOTOR_PID_KD);
    pid_init(&motorB, POSITION_PID, MOTOR_PID_KP, MOTOR_PID_KI, MOTOR_PID_KD);

    /* 固定两轮正方向：目标速度为正 = 前进（编码器计数递增），
     * 某轮实测反转时改对应宏的标定电平，不动控制逻辑 */
    motor_set_direction(1, MOTOR1_DIR_FORWARD);
    motor_set_direction(2, MOTOR2_DIR_FORWARD);

    // TODO: 10ms 定时器启动（循环内轮询或中断调度） —— 由接口块替换
    //       本骨架用 while(1) + delay_ms(XUNJI_TICK_MS) 产生 10ms 节拍；
    //       若电机内环 / IMU 间隙计时需要硬件定时器，改在中断里调 xunji_dispatch()。

    led_beep_on();              /* 上电声光自检 */
    delay_ms(50);
    led_beep_off();

    for (;;) {
        xunji_dispatch();
        // TODO: 10ms 节拍等待（如 delay_ms(10)） —— 由接口块替换
        delay_ms(XUNJI_TICK_MS);
    }
}

/*
 * ================= 赛题功能预留编写区（TODO，暂不实现，避免凭空造接口）=================
 * (1) A→B 直线段：灰度巡线 + 到 B 点停车 + 声光提示（本骨架的 FOLLOW/WAIT_LINE 已覆盖）。
 * (2) A→B→(半圆弧 40cm)→C→D→(半圆弧)→A：圆弧段需角度闭环，
 *     可用 imu.h 的 gyro_angle_raw（实际角度 = raw×0.1°）/ current_attitude.yaw 做航向环，
 *     角度环实例 angle（pid_t）由 pid_mspm0.h 提供；顶点判定可用 IMU 转过 ±90°/180° 触发。
 * (3) A→C→(弧)→B→D→(弧)→A：路径切换靠同一套角度环 + 顶点计数（segment 变量）。
 * (4) 按 (3) 路径 4 圈：在 XUNJI_WAIT_LINE 超时分支加 lap 计数（见该分支 TODO）。
 * 里程辅助：motor_encoder_read()（线数 MOTOR_BIANMAQI=260，轮径 MOTOR_WHEEL_D=48mm）
 * 可用于顶点精停与速度换算。以上若需落在 10ms 节拍内，请补进 xunji_dispatch() 对应 case。
 */