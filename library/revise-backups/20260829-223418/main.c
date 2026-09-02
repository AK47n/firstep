#include "motor.h"
#include "pid_mspm0.h"
#include "gray_track_mspm0.h"
#include "led.h"
#include "beep.h"
#include "delay.h"
#include "led_beep.h"
#include "imu.h"
#include <stdint.h>
#include <math.h>

// ===== 巡线状态机 =====
typedef enum {
    XUNJI_STOP,        /* 完成一圈后停车 */
    SEG_AB,            /* A→B 顶部直线 */
    SEG_BC,            /* B→C 右半圆弧 */
    SEG_CD,            /* C→D 底部直线 */
    SEG_DA             /* D→A 左半圆弧 */
} xunji_state_t;

static xunji_state_t xunji_state = SEG_AB;

// ===== 参数区 =====
#define SEG_AB_DISTANCE_CM (100.0f)
#define SEG_BC_DISTANCE_CM (125.6f)
#define SEG_CD_DISTANCE_CM (220.0f)
#define SEG_DA_DISTANCE_CM (125.6f)

#define SEG_AB_YAW_DELTA_DEG (0.0f)
#define SEG_BC_YAW_DELTA_DEG (-90.0f)
#define SEG_CD_YAW_DELTA_DEG (-90.0f)
#define SEG_DA_YAW_DELTA_DEG (90.0f)

#define SEG_ANGLE_TOLERANCE_DEG (20.0f)
#define XUNJI_ONE_LAP_TIMEOUT_MS (30 * 1000)

// 编码器平均脉冲换算距离（cm/脉冲）
#define DIST_PER_PULSE_CM (3.1415926f * MOTOR_WHEEL_D / 10.0f / MOTOR_BIANMAQI)

// 角度差归一化到 [-180°, 180°]
static float angle_diff(float a, float b)
{
    float diff = a - b;
    while (diff > 180.0f) diff -= 360.0f;
    while (diff < -180.0f) diff += 360.0f;
    return diff;
}

/*
 * 10ms 调度周期入口。
 * 多阶段路径状态机：每段巡线 + PID，使用 IMU 航向与编码器里程判断到达顶点。
 */
static void xunji_dispatch(void)
{
    static float segment_distance_cm = 0.0f;
    static float start_yaw = 0.0f;
    static uint32_t overall_timeout_ms = 0;
    static uint8_t seg_started = 0;

    // 整体一圈超时保护
    if (xunji_state != XUNJI_STOP) {
        overall_timeout_ms += 10;
        if (overall_timeout_ms >= XUNJI_ONE_LAP_TIMEOUT_MS) {
            motor_set_duty(0, 0);
            motor_set_duty(1, 0);
            xunji_state = XUNJI_STOP;
            return;
        }
    }

    switch (xunji_state) {
        case XUNJI_STOP:
            motor_set_duty(0, 0);
            motor_set_duty(1, 0);
            break;

        case SEG_AB:
        case SEG_BC:
        case SEG_CD:
        case SEG_DA:
        {
            float target_dist;
            float expected_delta;
            xunji_state_t next_state;

            switch (xunji_state) {
                case SEG_AB:
                    target_dist = SEG_AB_DISTANCE_CM;
                    expected_delta = SEG_AB_YAW_DELTA_DEG;
                    next_state = SEG_BC;
                    break;
                case SEG_BC:
                    target_dist = SEG_BC_DISTANCE_CM;
                    expected_delta = SEG_BC_YAW_DELTA_DEG;
                    next_state = SEG_CD;
                    break;
                case SEG_CD:
                    target_dist = SEG_CD_DISTANCE_CM;
                    expected_delta = SEG_CD_YAW_DELTA_DEG;
                    next_state = SEG_DA;
                    break;
                case SEG_DA:
                    target_dist = SEG_DA_DISTANCE_CM;
                    expected_delta = SEG_DA_YAW_DELTA_DEG;
                    next_state = XUNJI_STOP;
                    break;
                default:
                    target_dist = 0.0f;
                    expected_delta = 0.0f;
                    next_state = XUNJI_STOP;
                    break;
            }

            // 段起始：切换后第一拍记录当前航向并清零段里程
            if (!seg_started) {
                start_yaw = current_attitude.yaw;
                segment_distance_cm = 0.0f;
                seg_started = 1;
            }

            // 读取编码器（内部清零），累计段里程
            int32_t left_enc = 0, right_enc = 0;
            motor_encoder_read(&left_enc, &right_enc);
            float avg_pulse = ((float)left_enc + (float)right_enc) * 0.5f;
            segment_distance_cm += avg_pulse * DIST_PER_PULSE_CM;

            // 读取 IMU 航向，计算相对当前起始的航向变化
            float yaw_now = current_attitude.yaw;
            float yaw_delta = angle_diff(yaw_now, start_yaw);

            // 到达下一顶点：停车 + 声光提示 + 切换下一段
            if (segment_distance_cm >= target_dist &&
                fabsf(yaw_delta - expected_delta) < SEG_ANGLE_TOLERANCE_DEG) {
                motor_set_duty(0, 0);
                motor_set_duty(1, 0);
                led_beep_alarm(3, 200, 100);
                xunji_state = next_state;
                segment_distance_cm = 0.0f;
                start_yaw = current_attitude.yaw;
                seg_started = 0;
                break;
            }

            // 未到达：巡线 + PID 差速控制
            line_pid_track();
            motorA.now = (float)left_enc;
            motorB.now = (float)right_enc;
            pid_cal(&motorA);
            pid_cal(&motorB);

            int duty_left = limit_duty((int)motorA.out);
            int duty_right = limit_duty((int)motorB.out);
            if (duty_left < 0) duty_left = 0;
            if (duty_right < 0) duty_right = 0;
            motor_set_duty(0, (uint32_t)duty_left);
            motor_set_direction(0, 0);
            motor_set_duty(1, (uint32_t)duty_right);
            motor_set_direction(1, 0);
            break;
        }
    }
}

int main(void)
{
    gray_init();               // 灰度传感器
    motor_init(0);             // 左电机（motor_id=0）
    motor_init(1);             // 右电机（motor_id=1）
    pid_init(&motorA, POSITION_PID, 0.9f, 0.0f, 0.0f);
    pid_init(&motorB, POSITION_PID, 0.9f, 0.0f, 0.0f);
    pid_init(&line_pid, POSITION_PID, 3.4f, 0.0f, 0.0f);
    IMU_Init();                // IMU 初始化
    IMU_ConfigReportRate();    // 启动角度/角速度上报
    led_beep_init();           // 声光组合模块初始化

    for (;;) {
        xunji_dispatch();
        delay_ms(10);
    }
}