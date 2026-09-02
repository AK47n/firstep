#include "xunji.h"
#include "led.h"
#include "beep.h"
#include "led_beep.h"
#include "delay.h"

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

/* 状态切换时重置超时计数 */
static xunji_state_t last_state = XUNJI_STOP;
static uint32_t state_timeout_ms = 0;

/*
 * 10ms 调度周期入口（isr 或定时器回调调用）。
 * 读线 → 算偏差 → 差速控制；状态机只做最小化转移。
 */
static void xunji_dispatch(void) {
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
            if (gray != 0) {
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
            xunji_set_speed(left, right);

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