#include "xunji.h"
#include "led.h"
#include "beep.h"
#include "led_beep.h"
#include "delay.h"
#include "motor.h"

// ===== 编码器里程与速度控制参数 =====
// 编码器每脉冲对应轮子移动距离（mm）
#define PULSE_TO_MM  (3.141592653589793f * MOTOR_WHEEL_D / MOTOR_BIANMAQI)
// 采样周期（秒），与调度周期一致
#define SAMPLING_PERIOD_S 0.01f
// 满速 10ms 编码器脉冲增量（需按实际底盘标定）
#define MOTOR_MAX_DELTA 100
// 速度 PI 参数
#define SPEED_PI_KP 2.0f
#define SPEED_PI_KI 0.5f
#define SPEED_PI_OUT_MAX 50.0f

// ===== 全局里程与速度（供后续路径点判断） =====
float total_left_mm = 0.0f;
float total_right_mm = 0.0f;
float speed_left_mms = 0.0f;
float speed_right_mms = 0.0f;

// 速度 PI 积分状态
static float pid_integral_left = 0.0f;
static float pid_integral_right = 0.0f;

// ===== 巡线状态机 =====
typedef enum {
    XUNJI_STOP,        /* 等待启动（按键 / 上电复位） */
    XUNJI_FOLLOW,      /* 正常巡线中 */
    XUNJI_WAIT_LINE    /* 等待特定线型（如停车区） */
} xunji_state_t;

static xunji_state_t xunji_state = XUNJI_STOP;

// ===== 完整一圈路径状态机 =====
// 0=原有要求(2)：A→B→C→D→A
// 1=替代要求(3)：A→C→B→D→A（交叉路径）
static uint8_t path_mode = 1;

typedef enum {
    PHASE_AB = 0,   /* A→B 直线 */
    PHASE_BC,       /* B→C 右侧半圆弧 */
    PHASE_CB,       /* 替代路径：C→B 右侧半圆弧反向 */
    PHASE_BD,       /* 替代路径：B→D 直线 */
    PHASE_CD,       /* 原有：C→D 直线 */
    PHASE_DA,       /* D→A 左侧半圆弧 */
    PHASE_DONE      /* 回到 A 停车 */
} path_phase_t;

static path_phase_t path_phase = PHASE_AB;

// ===== TODO 参数区（按题面 / 实际底盘标定值填写）=====
// 基础速度（百分比制，0~100）
#define BASE_SPEED       45
// 巡线偏差增益（值越大转向越激进）
#define LINE_GAIN        4.0f
// 停车区判定连续帧数（按 10ms 调度周期换算）
#define STOP_LINE_FRAMES 3
// 状态转换安全超时（ms）：完整一圈要求不大于 30s，放宽到 40s
#define STATE_TIMEOUT_MS 40000
// 10ms 调度周期节拍（用于超时计数）
#define TIMEOUT_PERIOD_MS 10

// ===== 路径段里程阈值（单位 mm）=====
// A→B 段长度（mm），按实际场地标定（直线距离）
#define AB_DISTANCE_MM   1000.0f
// 半圆弧半径（mm）：题目给出 40cm
#define ARC_RADIUS_MM    400.0f
// 半圆弧长度
#define ARC_LEN_MM       (3.141592653589793f * ARC_RADIUS_MM)
// B→C 半圆弧段累计里程（原有路径 A→C 累计）
#define BC_DISTANCE_MM   (AB_DISTANCE_MM + ARC_LEN_MM)
// C→D 段累计里程（底部直线长 2200mm）
#define CD_DISTANCE_MM   (BC_DISTANCE_MM + 2200.0f)
// D→A 半圆弧段累计里程，即完成一圈的总里程（原有路径）
#define DA_DISTANCE_MM   (CD_DISTANCE_MM + ARC_LEN_MM)

// 替代路径（要求3）扩展阈值
// C→B 圆弧后累计里程
#define ALT_CB_MM        (BC_DISTANCE_MM + ARC_LEN_MM)
// B→D 直线后累计里程（TODO: 按实际 B→D 直线距离标定，暂取 1562mm）
#define ALT_BD_MM        (ALT_CB_MM + 1562.0f)
// D→A 圆弧后累计里程，即替代路径一圈总里程
#define ALT_DA_MM        (ALT_BD_MM + ARC_LEN_MM)

/* 状态切换时重置超时计数 */
static xunji_state_t last_state = XUNJI_STOP;
static uint32_t state_timeout_ms = 0;

// 多圈计数：初始 0，完成一圈加 1，达到 4 圈后停车
static uint8_t lap_count = 0;

/*
 * 速度 PI 控制器：
 * 目标速度（百分比） -> 期望 10ms 编码器增量 -> 反馈实际增量 -> 输出修正后速度
 */
static int speed_pi_control(int target_speed, int32_t actual_delta, float *integral)
{
    float target_delta = (float)target_speed * MOTOR_MAX_DELTA / 100.0f;
    float error = target_delta - (float)actual_delta;

    *integral += error * SAMPLING_PERIOD_S;
    if (*integral > 50.0f) *integral = 50.0f;
    if (*integral < -50.0f) *integral = -50.0f;

    float adjust = SPEED_PI_KP * error + SPEED_PI_KI * *integral;
    if (adjust > SPEED_PI_OUT_MAX) adjust = SPEED_PI_OUT_MAX;
    if (adjust < -SPEED_PI_OUT_MAX) adjust = -SPEED_PI_OUT_MAX;

    int out = (int)((float)target_speed + adjust);
    if (out > 100) out = 100;
    if (out < -100) out = -100;
    return out;
}

/*
 * 声光提示系统任务：
 * 根据累积里程与预置 A/B/C/D 点里程阈值比较，越过某点则声光提示一次并记录标志。
 * 阈值单位为 mm，需按实际赛道/底盘标定；A 点阈值设为完成一圈回到 A 时的总里程。
 * 替代路径（path_mode==1）下，声光提示改为在状态机切换处完成，此处直接返回。
 */
static void check_point_and_alert(void)
{
    if (path_mode == 1) return;

    /* A/B/C/D 点里程阈值：A=一圈总里程，B=到B点，C=到C点，D=到D点 */
    static const float thresholds_mm[4] = {
        DA_DISTANCE_MM,   /* A（回到起点） */
        AB_DISTANCE_MM,   /* B */
        BC_DISTANCE_MM,   /* C */
        CD_DISTANCE_MM    /* D */
    };
    /* 已提示标志位图：bit0=A，bit1=B，bit2=C，bit3=D */
    static uint8_t alerted_flags = 0;

    float avg_mm = (total_left_mm + total_right_mm) * 0.5f;

    for (uint8_t i = 0; i < 4; i++) {
        if ((avg_mm >= thresholds_mm[i]) && ((alerted_flags & (1u << i)) == 0u)) {
            alerted_flags |= (1u << i);
            led_beep_alarm(1, 100, 100);
        }
    }
}

/*
 * 10ms 调度周期入口（isr 或定时器回调调用）。
 * 读线 → 算偏差 → 差速控制；状态机只做最小化转移。
 * 同时读取编码器，计算增量、累积里程和速度，并进行速度 PI 闭环。
 */
static void xunji_dispatch(void) {
    // 读取编码器（读后清零）
    int32_t enc_left = 0, enc_right = 0;
    xunji_encoder_read(&enc_left, &enc_right);
    int32_t delta_left = enc_left;
    int32_t delta_right = enc_right;

    // 计算速度（mm/s）
    speed_left_mms = delta_left * PULSE_TO_MM / SAMPLING_PERIOD_S;
    speed_right_mms = delta_right * PULSE_TO_MM / SAMPLING_PERIOD_S;

    // 累积里程（mm）
    total_left_mm += delta_left * PULSE_TO_MM;
    total_right_mm += delta_right * PULSE_TO_MM;

    // 状态切换时重置超时计数
    if (xunji_state != last_state) {
        last_state = xunji_state;
        state_timeout_ms = 0;
    }
    state_timeout_ms += TIMEOUT_PERIOD_MS;

    // 读灰度线：返回 8 路位图，1 = 白区
    uint8_t gray = xunji_read_gray();

    switch (xunji_state) {
        case XUNJI_STOP:
            // TODO: 启动条件（检测到黑线自动启动；如有按键改用按键输入）
            // 多圈完成前允许启动，达到 4 圈后禁止再启动
            if ((gray == 0) && (lap_count < 4)) {
                xunji_state = XUNJI_FOLLOW;
                path_phase = PHASE_AB;
                led_beep_alarm(1, 100, 100);   // 启动声光提示
            }
            break;

        case XUNJI_FOLLOW:
        {
            // 巡线控制：加权质心偏航 → 差速输出
            float bias = xunji_centroid(LINE_GAIN);
            int left =  (int)(BASE_SPEED + bias);
            int right = (int)(BASE_SPEED - bias);

            // 速度限幅
            if (left > 100)  left = 100;
            if (left < -100) left = -100;
            if (right > 100)  right = 100;
            if (right < -100) right = -100;

            // 速度 PI 闭环：以巡线目标速度为给定，编码器增量为反馈，输出稳定速度
            left = speed_pi_control(left, delta_left, &pid_integral_left);
            right = speed_pi_control(right, delta_right, &pid_integral_right);

            xunji_set_speed(left, right);

            // 每经过 A/B/C/D 点时声光提示一次；替代路径下由状态机切换处提示
            check_point_and_alert();

            // 路径状态机：按里程阈值切换
            float avg_mm = (total_left_mm + total_right_mm) * 0.5f;

            switch (path_phase) {
                case PHASE_AB:
                    if (avg_mm >= AB_DISTANCE_MM) {
                        path_phase = PHASE_BC;
                        if (path_mode == 1) led_beep_alarm(1, 100, 100); // 到达 B
                    }
                    break;

                case PHASE_BC:
                    if (avg_mm >= BC_DISTANCE_MM) {
                        if (path_mode == 1) {
                            path_phase = PHASE_CB;
                            led_beep_alarm(1, 100, 100); // 到达 C
                        } else {
                            path_phase = PHASE_CD;
                        }
                    }
                    break;

                case PHASE_CB:
                    if (avg_mm >= ALT_CB_MM) {
                        path_phase = PHASE_BD;
                        led_beep_alarm(1, 100, 100); // 到达 B（第二次）
                    }
                    break;

                case PHASE_BD:
                    if (avg_mm >= ALT_BD_MM) {
                        path_phase = PHASE_DA;
                        led_beep_alarm(1, 100, 100); // 到达 D
                    }
                    break;

                case PHASE_CD:
                    if (avg_mm >= CD_DISTANCE_MM) {
                        path_phase = PHASE_DA;
                    }
                    break;

                case PHASE_DA:
                    if (path_mode == 1) {
                        if (avg_mm >= ALT_DA_MM) {
                            lap_count++;
                            if (lap_count >= 4) {
                                // 达到 4 圈：进入停止状态，声光提示并停车
                                path_phase = PHASE_DONE;
                                xunji_state = XUNJI_STOP;
                                xunji_set_speed(0, 0);
                                led_beep_alarm(1, 200, 200);
                            } else {
                                // 圈数未满：清空里程和 PID 积分，继续下一圈
                                path_phase = PHASE_AB;
                                total_left_mm = 0.0f;
                                total_right_mm = 0.0f;
                                pid_integral_left = 0.0f;
                                pid_integral_right = 0.0f;
                                state_timeout_ms = 0;
                                led_beep_alarm(1, 100, 100); // 到达 A
                            }
                        }
                    } else {
                        if (avg_mm >= DA_DISTANCE_MM) {
                            lap_count++;
                            if (lap_count >= 4) {
                                // 达到 4 圈：进入停止状态，声光提示并停车
                                path_phase = PHASE_DONE;
                                xunji_state = XUNJI_STOP;
                                xunji_set_speed(0, 0);
                                led_beep_alarm(1, 200, 200);
                            } else {
                                // 圈数未满：清空里程和 PID 积分，继续下一圈
                                path_phase = PHASE_AB;
                                total_left_mm = 0.0f;
                                total_right_mm = 0.0f;
                                pid_integral_left = 0.0f;
                                pid_integral_right = 0.0f;
                                state_timeout_ms = 0;
                            }
                        }
                    }
                    break;

                case PHASE_DONE:
                    xunji_set_speed(0, 0);
                    break;
            }

            // 安全兜底：巡线超时强制停止（一圈时限 30s，超时阈值已放宽至 40s）
            if (state_timeout_ms > STATE_TIMEOUT_MS) {
                state_timeout_ms = 0;
                xunji_state = XUNJI_STOP;
                xunji_set_speed(0, 0);
            }
            break;
        }

        case XUNJI_WAIT_LINE:
            // TODO: 停车保持 / 等待确认（按键复位或超时收车）
            xunji_set_speed(0, 0);
            if (state_timeout_ms > STATE_TIMEOUT_MS) {
                state_timeout_ms = 0;
                xunji_state = XUNJI_STOP;
            }
            break;
    }
}

/*
 * main() 骨架：初始化 → 调度循环（while(1) 内只调 xunji_dispatch）。
 */
int main(void) {
    // 模块初始化：LED → 蜂鸣器 → 组合模块 → 循迹/电机/编码器
    led_init(LED_RED);
    beep_init();
    led_beep_init();
    xunji_init();

    // TODO: 10ms 定时器启动（此处为循环内轮询节拍，使用 delay_ms(10)）
    led_beep_alarm(1, 100, 100); // 上电声光提示

    for (;;) {
        xunji_dispatch();
        delay_ms(10);
    }
}