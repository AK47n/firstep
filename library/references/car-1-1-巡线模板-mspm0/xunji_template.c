/**
 * ============================================================
 * xunji_template.c — 小车巡线逻辑可复用模板
 * ============================================================
 *
 * 【使用说明】
 * 1. 在文件顶部实现所有 "TODO: 平台适配" 标注的硬件接口函数
 * 2. 在定时中断中调用 xunji_timer_50ms_callback()
 * 3. 在主循环中调用对应的 Control_xxx() 函数
 * 4. 根据实际传感器数量调整 SENSOR_COUNT 和对应的权重表
 *
 * 【核心算法】加权质心法（Weighted Centroid）
 * 参考文献：xunji_logic_spec.md
 */

#include "xunji_template.h"
#include <stdbool.h>
#include <stdlib.h>   // abs()

// ============================================================
// 第一部分：配置常量（可按需调整）
// ============================================================

#define SENSOR_COUNT        8       // 灰度传感器数量
#define PWM_LIMIT           200     // PWM 输出限幅（百分比制）
#define GAIN_NORMAL         3.4f    // 普通速度巡线增益
#define GAIN_HIGH           7.0f    // 高速巡线增益
#define GAIN_LOW            3.0f    // 低速巡线增益
#define SPEED_MIDDLE        20.0f   // 基准速度
#define ENCODER_TO_SPEED    3.0f    // 编码器脉冲 → 速度转换系数

// PID 参数（增量式）
#define KP                  0.9f
#define KI                  0.0f
#define KD                  0.0f

// ============================================================
// 第二部分：全局变量
// ============================================================

// --- 编码器 ---
static volatile int32_t g_encoder_count_left  = 0;  // 左轮脉冲累计
static volatile int32_t g_encoder_count_right = 0;  // 右轮脉冲累计
static volatile int32_t g_encoder_val_left    = 0;  // 50ms 周期内的左轮速度
static volatile int32_t g_encoder_val_right   = 0;  // 50ms 周期内的右轮速度

// --- 状态机 ---
static volatile int   flag_area_black   = 1;   // 1=在黑线区域, 0=在白区
static volatile int   segment_counter   = 1;   // 段计数器 n（见规格说明）
static volatile int   mode_step_count   = 0;   // 模式步骤计数器 m
static volatile int   white_flag        = 0;   // 当前在白区标志
static volatile int   white_flag1       = 0;   // 模式2用白区标志
static volatile int   white_flag2       = 0;   // 模式3用白区标志

// --- 延时/防抖 ---
static volatile int   time_begin       = 0;
static volatile int   time_count       = 0;
static volatile int   time_begin1      = 0;
static volatile int   time_count1      = 0;
static volatile int   time_begin2      = 0;
static volatile int   time_count2      = 0;

// --- LED ---
static volatile int   led_begin        = 0;
static volatile int   led_count        = 0;
static volatile int   led_flag         = 0;
static volatile int   led_flag1        = 0;
static volatile int   led_flag2        = 0;

// --- 陀螺仪 ---
static float yaw = 0.0f;  // 由陀螺仪中断更新

// --- PWM启动控制 ---
static volatile int   pwm_start        = 1;
static volatile int   stop_flag_a      = 0;

// ============================================================
// 第三部分：硬件抽象接口（TODO: 平台适配 — 需要实现以下函数）
// ============================================================

/*
 * 读取第 index 个灰度传感器（0 = P1, 1 = P2, ... 7 = P8）
 * 返回值: true = 检测到黑线, false = 白色地面
 */
extern bool hal_read_grayscale(uint8_t index);

/*
 * 设置左/右电机
 * pwm > 0: 前进，占空比 = pwm
 * pwm < 0: 后退，占空比 = |pwm|
 */
extern void hal_set_motor_left(int16_t pwm);
extern void hal_set_motor_right(int16_t pwm);

/*
 * 设置 LED 指示灯
 */
extern void hal_set_led(bool on);

/*
 * 使能/禁能电机（STBY引脚）
 */
extern void hal_motor_enable(bool enable);

/*
 * 获取陀螺仪偏航角（-180° ~ +180°）
 */
extern float hal_get_yaw(void);

// ============================================================
// 第四部分：核心巡线算法（加权质心法）
// ============================================================

/**
 * 加权质心巡线算法
 *
 * 原理:
 *   每个灰度传感器有一个固定位置权重，检测到黑线的传感器
 *   权重累加后除以检测到的传感器数量，得到黑线的质心位置。
 *   质心偏离中心的程度 × gain = 差速偏置量（bias）
 *
 * @param gain  增益系数，值越大转向越激进（典型值 3.0~7.0）
 * @return      bias值: >0 线偏右需右转, <0 线偏左需左转, =0 未检测到线
 *
 * 传感器权重映射（SENSOR_COUNT=8时）:
 *   index:  0    1    2    3    4    5    6    7
 *   P编号:  P1   P2   P3   P4   P5   P6   P7   P8
 *   权重:   -7   -5   -3   -1   +1   +3   +5   +7
 *
 * 通用公式（任意数量传感器）:
 *   权重 = (i - (N-1)/2) * 2, 其中 i=0..N-1, N必须为奇数
 */
float xunji_centroid(float gain)
{
    int32_t sum = 0;
    int32_t cnt = 0;

    for (uint8_t i = 0; i < SENSOR_COUNT; i++)
    {
        if (hal_read_grayscale(i))          // 读到黑线
        {
            // 通用权重公式：传感器索引 → 对称权重
            // 例如 N=8: i=0→-7, i=1→-5, i=2→-3, i=3→-1,
            //           i=4→+1, i=5→+3, i=6→+5, i=7→+7
            sum += (int32_t)((i - (SENSOR_COUNT - 1) / 2.0f) * 2);
            cnt++;
        }
    }

    if (cnt == 0)
        return 0.0f;

    // 质心 = 加权平均 / cnt, 取反后乘以增益
    // 取反原因: sum>0表示线偏右→应右转，但差速公式中 bias>0 对应右转
    //            即 bias = -(sum/cnt) * gain
    return -(float)sum / cnt * gain;
}

// ============================================================
// 第五部分：PID 速度控制（增量式）
// ============================================================

typedef struct
{
    float kp, ki, kd;
    float last_bias;
    float last2_bias;
    float pwm_out;
} PID_Controller;

static PID_Controller pid_left  = { KP, KI, KD, 0, 0, 0 };
static PID_Controller pid_right = { KP, KI, KD, 0, 0, 0 };

/**
 * 增量式PID控制器
 *
 * 增量公式:
 *   Δu = Kp*(e(k)-e(k-1)) + Ki*e(k) + Kd*(e(k)-2e(k-1)+e(k-2))
 *   u(k) = u(k-1) + Δu
 */
float PID_compute(PID_Controller *pid, float current, float target)
{
    float bias = target - current;

    pid->pwm_out += pid->kp * (bias - pid->last_bias)
                  + pid->ki * bias
                  + pid->kd * (bias - 2 * pid->last_bias + pid->last2_bias);

    pid->last2_bias = pid->last_bias;
    pid->last_bias  = bias;

    return pid->pwm_out;
}

// ============================================================
// 第六部分：工具函数
// ============================================================

/** PWM 输出限幅 */
static float pwm_clamp(float value, float max_val, float min_val)
{
    if (value > max_val) return max_val;
    if (value < min_val) return min_val;
    return value;
}

/** 检测是否所有传感器都在白色区域（都没检测到黑线） */
static bool is_all_white(void)
{
    for (uint8_t i = 0; i < SENSOR_COUNT; i++)
        if (hal_read_grayscale(i))
            return false;
    return true;
}

// ============================================================
// 第七部分：电机输出
// ============================================================

/**
 * 设置左右电机，自动处理方向和PWM
 */
static void set_motors(int16_t motor_left, int16_t motor_right)
{
    hal_set_motor_left(motor_left);
    hal_set_motor_right(motor_right);
}

/**
 * 差速驱动：将 bias 分配到左右轮
 *
 * 差速公式:
 *   target_left  = speed_middle + bias   (bias>0: 左轮快 = 右转)
 *   target_right = speed_middle - bias   (bias>0: 右轮慢 = 右转)
 *
 * 物理含义:
 *   - 线偏右（bias>0）→ 右轮减速、左轮加速 → 车右转跟上黑线
 *   - 线偏左（bias<0）→ 左轮减速、右轮加速 → 车左转跟上黑线
 */
static void differential_drive(float speed_middle, float bias)
{
    float target_left  = speed_middle + bias;
    float target_right = speed_middle - bias;

    float current_left  = (float)g_encoder_val_left  / ENCODER_TO_SPEED;
    float current_right = (float)g_encoder_val_right / ENCODER_TO_SPEED;

    int16_t motor_left  = (int16_t)pwm_clamp(
        PID_compute(&pid_left, current_left, target_left),
        PWM_LIMIT, -PWM_LIMIT);

    int16_t motor_right = (int16_t)pwm_clamp(
        PID_compute(&pid_right, current_right, target_right),
        PWM_LIMIT, -PWM_LIMIT);

    set_motors(motor_left, motor_right);
}

// ============================================================
// 第八部分：模式控制函数
// ============================================================

/**
 * 模式1: ABCDA — 单圈巡线（含白区掉头）
 *
 * 赛道布局:  A → B → C → D → A（闭环）
 *
 * 状态机:
 *   - 黑线区域: 用加权质心法巡线（xunji_centroid）
 *   - 白色区域: 用陀螺仪保持方向或掉头
 *
 * 段计数规则:
 *   每个黑区+1, 每个白区+1, m>=6时停车
 */
void Control_ABCDA(void)
{
    float bias = 0.0f;

    // ----- LED 指示 -----
    hal_set_led(led_flag == 1);

    // ----- 白区/黑区检测与状态切换 -----
    if (is_all_white())
        time_begin = 1;    // 初步认定进入白区，启动延时确认
    else
        white_flag = 0;    // 不在白区

    // ----- 白区处理 -----
    if (white_flag == 1)
    {
        led_flag2 = 0;

        if (led_flag1 == 0)   // 第一帧进入白区
        {
            led_flag1 = 1;
            led_begin = 1;
            mode_step_count++;  // m++
        }

        // 段奇偶判断：偶数为掉头段，奇数为直行段
        if (segment_counter % 2 == 0)
        {
            // 掉头: 以error为参考角度，消除yaw偏差
            float error = 180.0f;
            if (yaw < 0)
                bias = error - fabsf(yaw);
            else
                bias = yaw - error;
        }
        else
        {
            // 直行通过白区：保持当前yaw方向
            bias = yaw;
        }

        flag_area_black = 0;
    }
    // ----- 黑区处理（巡线） -----
    else
    {
        led_flag1 = 0;

        if (led_flag2 == 0)   // 第一帧进入黑区
        {
            led_flag2 = 1;
            led_begin = 1;
            mode_step_count++;  // m++
        }

        if (flag_area_black == 0)  // 刚从白区进入黑区
        {
            flag_area_black = 1;
            segment_counter++;     // n++
        }

        // ★★★ 核心：加权质心巡线 ★★★
        bias = xunji_centroid(GAIN_NORMAL);

        white_flag = 0;
    }

    // ----- 差速驱动输出 -----
    differential_drive(SPEED_MIDDLE, bias);

    // ----- 停车判断 -----
    if (mode_step_count >= 6)
    {
        set_motors(1, 1);   // 微弱PWM（等效停车）
        time_begin = 0;
    }
}

/**
 * 模式2: ACBDA — 含180°固定角度掉头
 *
 * 与 ABCDA 的区别：
 *   - 偶数段（掉头段）不依赖error计算，而是直接偏移103°
 *   - bias = Yaw + 103（固定角度掉头）
 */
void Control_ACBDA(void)
{
    float bias = 0.0f;

    hal_set_led(led_flag == 1);

    // ----- 白区检测 -----
    if (is_all_white())
        time_begin1 = 1;
    else
        white_flag1 = 0;

    // ----- 白区处理 -----
    if (white_flag1 == 1)
    {
        led_flag2 = 0;

        if (led_flag1 == 0)
        {
            led_flag1 = 1;
            led_begin = 1;
            mode_step_count++;
        }

        if (segment_counter % 2 == 0)
            bias = yaw + 103.0f;   // 固定角度掉头
        else
            bias = yaw;            // 直行

        flag_area_black = 0;
    }
    // ----- 黑区处理（巡线） -----
    else
    {
        led_flag1 = 0;

        if (led_flag2 == 0)
        {
            led_flag2 = 1;
            led_begin = 1;
            mode_step_count++;
        }

        if (flag_area_black == 0)
        {
            flag_area_black = 1;
            segment_counter++;
        }

        bias = xunji_centroid(GAIN_NORMAL);
        white_flag1 = 0;
    }

    differential_drive(SPEED_MIDDLE, bias);

    if (mode_step_count >= 6)
    {
        set_motors(1, 1);
        time_begin = 0;
    }
}

/**
 * 模式3: ACBDAx4 — 模式2的四圈重复
 *
 * 与 ACBDA 逻辑完全一致，仅停车条件改为 m >= 18
 */
void Control_ACBDAx4(void)
{
    float bias = 0.0f;

    if (mode_step_count == 18)
        hal_motor_enable(false);

    hal_set_led(led_flag == 1);

    if (is_all_white())
        time_begin2 = 1;
    else
        white_flag2 = 0;

    if (white_flag2 == 1)
    {
        led_flag2 = 0;

        if (led_flag1 == 0)
        {
            led_flag1 = 1;
            led_begin = 1;
            mode_step_count++;
        }

        if (segment_counter % 2 == 0)
            bias = yaw + 103.0f;
        else
            bias = yaw;

        flag_area_black = 0;
    }
    else
    {
        led_flag1 = 0;

        if (led_flag2 == 0)
        {
            led_flag2 = 1;
            led_begin = 1;
            mode_step_count++;
        }

        if (flag_area_black == 0)
        {
            flag_area_black = 1;
            segment_counter++;
        }

        bias = xunji_centroid(GAIN_NORMAL);
        white_flag2 = 0;
    }

    differential_drive(SPEED_MIDDLE, bias);

    if (mode_step_count == 18)
    {
        set_motors(1, 1);
        time_begin = 0;
    }
}

/**
 * 模式0: AB — 纯陀螺仪直行模式
 *
 * 全程用 Yaw 作为 bias，不依赖灰度传感器巡线。
 * 检测到黑线 → 亮灯停车。
 */
void Control_AB(void)
{
    float bias = yaw;

    if (!is_all_white() && stop_flag_a == 0)
    {
        time_begin = 0;
        pwm_start  = 0;
        led_begin  = 1;
        stop_flag_a = 1;
    }

    hal_set_led(led_flag == 1);

    if (pwm_start == 1)
        differential_drive(SPEED_MIDDLE, bias);
    else
        set_motors(1, 1);
}

// ============================================================
// 第九部分：定时中断回调（需要在外部的50ms定时中断中调用）
// ============================================================

/**
 * 50ms 定时中断回调
 *
 * 职责:
 *   1. 捕获编码器速度值（脉冲/50ms）
 *   2. 处理白区确认延时
 *   3. 处理LED延时
 *
 * 调用频率: 20Hz（每50ms一次）
 */
void xunji_timer_50ms_callback(void)
{
    // ---- 编码器速度采样 ----
    g_encoder_val_left  = g_encoder_count_left;
    g_encoder_count_left  = 0;
    g_encoder_val_right = g_encoder_count_right;
    g_encoder_count_right = 0;

    // ---- 白区确认延时（模式1） ----
    // 需要连续2个周期都全白才确认进入白区（防抖）
    if (time_begin == 1)
    {
        if (time_count == 2)
        {
            white_flag  = 1;
            time_begin  = 0;
            time_count  = 0;
        }
        time_count++;
    }

    // ---- LED 延时（亮10个周期=500ms后自动熄灭） ----
    if (led_begin == 1)
    {
        led_flag = 1;
        if (led_count == 10)
        {
            led_flag  = 0;
            led_begin = 0;
            led_count = 0;
        }
        led_count++;
    }
}

/**
 * 10ms 定时中断回调
 *
 * 处理模式2和模式3的白区确认延时（不同的延时阈值）
 */
void xunji_timer_10ms_callback(void)
{
    // ---- 白区确认延时（模式2） ----
    // 需要连续3个周期（30ms）才确认
    if (time_begin1 == 1)
    {
        if (time_count1 == 3)
        {
            white_flag1 = 1;
            time_begin1 = 0;
            time_count1 = 0;
        }
        time_count1++;
    }

    // ---- 白区确认延时（模式3） ----
    // 需要连续19个周期（190ms）才确认
    if (time_begin2 == 1)
    {
        if (time_count2 == 19)
        {
            white_flag2 = 1;
            time_begin2 = 0;
            time_count2 = 0;
        }
        time_count2++;
    }
}

// ============================================================
// 第十部分：编码器中断回调
// ============================================================

/**
 * 编码器A/B相上升沿中断
 *
 * 正交解码：A相和B相相差90°，通过判断另一相的电平
 * 来确定旋转方向，实现正反转双向计数。
 *
 * 调用频率: 随转速变化（高速时可达数kHz）
 */
void xunji_encoder_callback(uint8_t channel, bool phase_a_rise, bool phase_b_level)
{
    if (channel == 0)  // 左轮编码器
    {
        if (phase_a_rise)
        {
            if (!phase_b_level)
                g_encoder_count_left--;
            else
                g_encoder_count_left++;
        }
        else  // phase_b_rise
        {
            if (!phase_a_rise)  // 此处 phase_a_rise 实为 A相电平
                g_encoder_count_left++;
            else
                g_encoder_count_left--;
        }
    }
    else  // 右轮编码器
    {
        if (phase_a_rise)
        {
            if (!phase_b_level)
                g_encoder_count_right--;
            else
                g_encoder_count_right++;
        }
        else
        {
            if (!phase_a_rise)  // A相电平
                g_encoder_count_right++;
            else
                g_encoder_count_right--;
        }
    }
}

// ============================================================
// 第十一部分：陀螺仪数据更新
// ============================================================

/**
 * 由陀螺仪UART中断调用，更新偏航角
 */
void xunji_update_yaw(float new_yaw)
{
    yaw = new_yaw;
}

// ============================================================
// 第十二部分：状态重置
// ============================================================

/**
 * 模式切换或重新开始时调用
 */
void xunji_reset_state(void)
{
    flag_area_black  = 1;
    segment_counter  = 1;
    mode_step_count  = 0;
    white_flag       = 0;
    white_flag1      = 0;
    white_flag2      = 0;
    time_begin       = 0;
    time_count       = 0;
    time_begin1      = 0;
    time_count1      = 0;
    time_begin2      = 0;
    time_count2      = 0;
    led_begin        = 0;
    led_count        = 0;
    led_flag         = 0;
    led_flag1        = 0;
    led_flag2        = 0;
    pwm_start        = 1;
    stop_flag_a      = 0;

    // 重置PID状态
    pid_left.last_bias   = 0;
    pid_left.last2_bias  = 0;
    pid_left.pwm_out     = 0;
    pid_right.last_bias  = 0;
    pid_right.last2_bias = 0;
    pid_right.pwm_out    = 0;
}
