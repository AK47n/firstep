/*
 * main.c —— 2024 电赛 H 题（自动行驶小车）主骨架
 * 平台：TI MSPM0G3507（地猛星） + TB6612 双电机 + 8 路灰度 + 编码器
 *
 * 题型框架：line_follow（car 1.1 巡线模板 mspm0）
 *   状态机枚举 / 调度循环 / 框架函数名保持原样，只在 TODO 位填入本工程
 *   所选模块（motor / pid_mspm0 / gray_track_mspm0 / led / beep / led_beep /
 *   delay / ntb_time）中真实存在的接口。
 *
 * 驱动选型说明：
 *   motor(TB6612) 与 l298n 为互替驱动，本骨架采用 motor —— 题面要求走 40cm
 *   半圆弧、投影不得脱离圆弧，必须闭环（motor 带编码器读数 API）；
 *   l298n 无编码器闭环，仅作备用（如需改用：l298n_init / l298n_set_duty /
 *   l298n_set_direction，并删除编码器测速段）。
 */

#include "motor.h"
#include "pid_mspm0.h"
#include "gray_track_mspm0.h"
#include "ntb_time.h"
#include "led.h"          /* 已含 led_instances.h：LED_CHANNEL_COUNT / LED_RED */
#include "beep.h"
#include "led_beep.h"
#include "delay.h"

/* ============================================================
 * TODO 参数区（全部为待标定的实测值，勿凭猜写死）
 * ============================================================ */
#define TICK_MS             10u      /* 调度周期 ms（框架约定 10ms 节拍） */
#define ENCODER_TO_SPEED    1.0f     /* 编码器脉冲 → 速度换算系数
                                      * （线数 MOTOR_BIANMAQI=260、轮径
                                      *   MOTOR_WHEEL_D=48mm，按 10ms 采样周期换算） */
#define SPEED_KP            0.9f     /* 速度环 P（增量式 / 位置式见 pid_mode） */
#define SPEED_KI            0.0f     /* 速度环 I */
#define SPEED_KD            0.0f     /* 速度环 D */
#define LINE_KP             3.4f     /* 巡线环 P（line_pid_track 内部使用） */
#define LINE_KI             0.0f     /* 巡线环 I */
#define LINE_KD             0.0f     /* 巡线环 D */
#define STOP_WHITE_FRAMES   5        /* 停车区判定：连续 N 帧「全白 / 丢线」特征
                                      * 5 帧 × 10ms = 50ms 消抖 */
#define RUN_TIMEOUT_MS      30000    /* 状态转换安全超时 ms（第 2 问一圈上限 30s，
                                      * 兜底禁止死等） */
#define STOP_BEEP_MS        200u     /* 经过 A/B/C/D 点声光提示时长 ms */

/* 电机编号约定（motor.h 未提供 ID 宏，此处为 main.c 本地约定）：
 * TODO: 与实车接线核对 0/1 分别对应左轮 / 右轮 */
#define MOTOR_ID_LEFT       0u
#define MOTOR_ID_RIGHT      1u

/* ===== 巡线状态机（框架原样保留）===== */
typedef enum {
    XUNJI_STOP,        /* 等待启动（按键 / 上电复位） */
    XUNJI_FOLLOW,      /* 正常巡线中 */
    XUNJI_WAIT_LINE    /* 等待特定线型（如停车区） */
} xunji_state_t;

static xunji_state_t xunji_state = XUNJI_STOP;

/* 框架约定的调度状态（无按键模块，启用计时与消抖，均被后续代码读取） */
static int64_t run_start_ms = 0;   /* 本段起跑时间戳（超时兜底用） */
static int     white_cnt    = 0;   /* 连续全白 / 丢线帧计数（停车区消抖） */

/*
 * 10ms 调度周期入口（主循环节拍或定时器中断调用）。
 * 读线 → 算偏差 → 差速控制；状态机只做最小化转移。
 */
static void xunji_dispatch(void)
{
    int32_t enc_left  = 0;
    int32_t enc_right = 0;

    switch (xunji_state) {
        case XUNJI_STOP:
            /* 等待启动：所选模块中没有按键接口。
             * TODO: 若补充按键模块，在此读取并消抖后再启动 */
            /* 上电后直接起步；起跑时间戳从这里开始（题面计时用） */
            run_start_ms = get_time_stamp_ms();
            xunji_state = XUNJI_FOLLOW;
            break;

        case XUNJI_FOLLOW:
            /* 1) 读线 → 偏差 → 差速目标：
             *    line_pid_track() 内部调用 line_error_calc()（灰度偏差）、
             *    all_white_detect()（丢线保持），并写 motorA/motorB.target */
            line_pid_track();

            /* 2) 编码器测速 → 速度环：
             *    motor_encoder_read() 读并清零计数（GROUP1_IRQHandler 累加），
             *    速度换算按 10ms 采样周期由调用方完成 */
            motor_encoder_read(&enc_left, &enc_right);
            motorA.now = (float)enc_left  * ENCODER_TO_SPEED;
            motorB.now = (float)enc_right * ENCODER_TO_SPEED;
            pid_cal(&motorA);
            pid_cal(&motorB);
            pidout_limit(&motorA);
            pidout_limit(&motorB);

            /* 3) 输出到电机：方向 + 占空比（题面只许前进，负输出仅用于收敛） */
            if (motorA.out >= 0.0f) {
                motor_set_direction(MOTOR_ID_LEFT, 0u);   /* TODO: 0/1 与正/反转的
                                                           * 对应关系按实车确认 */
            } else {
                motor_set_direction(MOTOR_ID_LEFT, 1u);
            }
            motor_set_duty(MOTOR_ID_LEFT, (uint32_t)limit_duty((int)motorA.out));

            if (motorB.out >= 0.0f) {
                motor_set_direction(MOTOR_ID_RIGHT, 0u);  /* TODO: 同上 */
            } else {
                motor_set_direction(MOTOR_ID_RIGHT, 1u);
            }
            motor_set_duty(MOTOR_ID_RIGHT, (uint32_t)limit_duty((int)motorB.out));

            /* 4) 停车区判定（连续 N 帧全白 / 丢线）+ 安全超时兜底 */
            if (all_white_detect()) {
                white_cnt++;
            } else {
                white_cnt = 0;
            }
            if ((white_cnt >= STOP_WHITE_FRAMES) ||
                ((get_time_stamp_ms() - run_start_ms) > (int64_t)RUN_TIMEOUT_MS)) {
                white_cnt = 0;
                xunji_state = XUNJI_WAIT_LINE;
            }
            break;

        case XUNJI_WAIT_LINE:
            /* 停车：占空比置零（题面要求停车点地面投影覆盖圆弧顶点） */
            motor_set_duty(MOTOR_ID_LEFT, 0u);
            motor_set_duty(MOTOR_ID_RIGHT, 0u);

            /* 声光提示：每经过 A/B/C/D 点一次。
             * 用非阻塞开关 + 一次短延时，勿在 FOLLOW 高频路径里调阻塞式提示 */
            led_beep_on();
            delay_ms(STOP_BEEP_MS);
            led_beep_off();

            /* TODO: 多段 / 多圈（第 2 / 3 / 4 问）在此编排下一段路径：
             *       xunji_state = XUNJI_FOLLOW;
             *       run_start_ms = get_time_stamp_ms();   // 重新计时
             *       white_cnt = 0;
             *       单段测试（第 1 问）停在本状态即可 */
            break;
    }
}

/*
 * main() 骨架：初始化 → 调度循环（while(1) 内只调 xunji_dispatch）。
 */
int main(void)
{
    /* ---- 初始化序列：先指示 → 再传感 → 再执行器 → 后算法参数 ---- */

    /* 1) 声光提示（上电指示 / 经过顶点提示共用） */
    led_init(LED_RED);      /* 单实例工程唯一 LED 通道：LED_RED = 0（PA15，LED_BEEP 组） */
    beep_init();            /* 蜂鸣器 */
    led_beep_init();        /* LED + 蜂鸣器组合层（依赖上两步） */

    /* 2) 灰度巡线传感器（8 路，通道宏 D1..D8 / digtal() 见 gray_track_mspm0.h） */
    gray_init();

    /* 3) 双电机（TB6612 + 编码器）：每路单独初始化 */
    motor_init(MOTOR_ID_LEFT);
    motor_init(MOTOR_ID_RIGHT);

    /* 4) PID 参数：速度环（左右各一）+ 巡线环 */
    pid_init(&motorA,   POSITION_PID, SPEED_KP, SPEED_KI, SPEED_KD);
    pid_init(&motorB,   POSITION_PID, SPEED_KP, SPEED_KI, SPEED_KD);
    pid_init(&line_pid, POSITION_PID, LINE_KP,  LINE_KI,  LINE_KD);
    // TODO: 角度环 angle（pid_mspm0.h 已 extern）——若加陀螺仪闭环，在此
    //       pid_init(&angle, POSITION_PID, <P>, <I>, <D>) 并在 FOLLOW 里喂 now

    /* 5) 上电声光提示（一次） */
    led_beep_alarm(1u, 100u, 100u);

    // TODO: 10ms 定时器启动 —— 本骨架用主循环 delay_ms(TICK_MS) 轮询节拍；
    //       若改中断调度，请在定时器中断里调 xunji_dispatch() 并删除循环内 delay_ms

    for (;;) {
        xunji_dispatch();
        delay_ms(TICK_MS);   /* 10ms 节拍等待 */
    }
}

/* ============================================================
 * 赛题路径段编排 —— 预留编写区（TODO，纯注释，无变量声明）
 *
 * 场地图：A(左上)—B(右上) 顶边 100cm；D(左下)—C(右下) 底边 220cm；
 *         左右端为 R=40cm 半圆弧；弧线宽约 1.8cm，线外无任何标记。
 *
 * 第（1）问：A → 直线 → B 停车，声光提示，≤15s
 *   段序列：{ 直行跟线, 直到 B 点特征 } → 停车 + 声光
 *
 * 第（2）问：A → B(直) → C(右半弧) → D(直) → A(左半弧) 停车，≤30s
 *   段序列：直/弧/直/弧 四段，每段到点停车 + 声光一次
 *
 * 第（3）问：A → C(直) → B(左半弧) → D(直) → A(右半弧) 停车，≤40s
 *   段序列：直/弧/直/弧，弧段方向与第（2）问相反（小车需掉头布线或反向跑弧）
 *
 * 第（4）问：第（3）问路径连跑 4 圈后停车，用时越少越好
 *   在 WAIT_LINE 里把圈计数 +1，未满 4 圈则重新起步（重置 run_start_ms）
 *
 * 待编排的接口调用（均为已存在接口，实现时直接填进 WAIT_LINE 的 TODO 位）：
 *   - 顶点识别：gray_track_mspm0.h 的 digtal(channel) / all_white_detect()
 *   - 圆弧段：line_pid_track() 连续输出（弧线为黑线，灰度仍可循迹）
 *   - 计时：ntb_time.h 的 get_time_stamp_ms()
 *   - 提示：led_beep.h 的 led_beep_on() / led_beep_off() / led_beep_alarm()
 *   - 停车：motor.h 的 motor_set_duty(id, 0)
 * ============================================================ */