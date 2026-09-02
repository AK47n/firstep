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

// ===== TODO 参数区（按题面 / 实际底盘标定值填写）=====
// 基础速度（百分比制，0~100）
#define BASE_SPEED       45
// 巡线偏差增益（值越大转向越激进）
#define LINE_GAIN        4.0f
// 停车区判定连续帧数（按 10ms 调度周期换算）
#define STOP_LINE_FRAMES 3
// 状态转换安全超时（ms）
#define STATE_TIMEOUT_MS 3000
// 10ms 调度周期节拍（用于超时计数）
#define TIMEOUT_PERIOD_MS 10
// A→B 段长度（mm），需按实际场地标定（直线距离）
#define AB_DISTANCE_MM   1000.0f

/* 状态切换时重置超时计数 */
static xunji_state_t last_state = XUNJI_STOP;
static uint32_t state_timeout_ms = 0;

// A→B 停车标志：到达 AB 段长度后置 1，防止 STOP 状态再次自动启动
static uint8_t ab_arrived = 0;

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
 */
static void check_point_and_alert(void)
{
    /* A/B/C/D 点里程阈值（示例值，实际需按场地标定）：
     * A=一圈总里程，B=到B点，C=到C点，D=到D点 */
    static const float thresholds_mm[4] = {
        5713.0f,   /* A（回到起点） */
        1000.0f,   /* B */
        2256.0f,   /* C */
        4456.0f    /* D */
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
            if ((gray != 0) && (!ab_arrived)) {
                xunji_state = XUNJI_FOLLOW;
                led_beep_alarm(1, 100, 100);   // 启动声光提示
            }
            break;

        case XUNJI_FOLLOW:
        {
            // 巡线控制：加权质心偏航 → 差速输出
            float bias = xunji_centroid(LINE_GAIN);
            int left =  (int)(BASE_SPEED + bias);
            int right = (int)(BASE_SPEED - bias);

            // TODO: 速度限幅（可根据实际电机能力调整）
            if (left > 100)  left = 100;
            if (left < -100) left = -100;
            if (right > 100)  right = 100;
            if (right < -100) right = -100;

            // 速度 PI 闭环：以巡线目标速度为给定，编码器增量为反馈，输出稳定速度
            left = speed_pi_control(left, delta_left, &pid_integral_left);
            right = speed_pi_control(right, delta_right, &pid_integral_right);

            xunji_set_speed(left, right);

            // A→B 直线行驶：累积里程达到 AB 段长度时停车
            float avg_mm = (total_left_mm + total_right_mm) * 0.5f;
            if (avg_mm >= AB_DISTANCE_MM) {
                ab_arrived = 1;
                xunji_state = XUNJI_STOP;
                xunji_set_speed(0, 0);
                led_beep_alarm(1, 200, 200); // 到达 B 点声光停车提示
                break;
            }

            // 声光提示：越过 A/B/C/D 点时报警一次
            check_point_and_alert();

            // TODO: 停车区特征判定需按实际赛道标定，此处暂按全白（0xFF）作为示例
            static uint8_t stop_frames = 0;
            if (gray == 0xFFu) {
                stop_frames++;
                if (stop_frames >= STOP_LINE_FRAMES) {
                    stop_frames = 0;
                    state_timeout_ms = 0;
                    xunji_state = XUNJI_WAIT_LINE;
                    xunji_set_speed(0, 0);
                    led_beep_alarm(1, 200, 200); // 到达停车区声光提示
                    break;
                }
            } else {
                stop_frames = 0;
            }

            // 安全兜底：巡线超时强制停止
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