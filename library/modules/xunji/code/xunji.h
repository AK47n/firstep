#ifndef __XUNJI_H_
#define __XUNJI_H_
#include "ti_msp_dl_config.h"
#include <stdint.h>

/* ===== 2024H 巡线题专用（mspm0，car xunji 真机工程移植）=====
 * 白区计数路口检测 + AB/ABCDA/ACBDA/ACBDAx4 模式状态机 + 加权质心巡线
 * + 声光（LED）提示。源：sources/car/car xunji/control.c（原生 mspm0 真机）。
 *
 * 调度：真机为 50ms/10ms 定时中断内做编码器采样 / 白区消抖 / LED 时序，
 * 移植后拆为 xunji_tick_50ms() / xunji_tick_10ms()，由 main 周期调用
 * （MOTOR_PID_INST_IRQHandler 已被 motor 模块占用，参考 pid_mspm0 先例
 * 自建定时器中断或主循环分频调用）；Control_xxx 在主循环持续调用。
 */

void xunji_init(void);

/* 四个模式状态机（真机 empty.c 主循环按 mode 调用） */
void Control_AB(void);        /* 模式一：陀螺仪直行，见黑线停车 */
void Control_ABCDA(void);     /* 模式二：A→B→C→D→A 一圈 */
void Control_ACBDA(void);     /* 模式三：A→C→B→D→A 反向一圈 */
void Control_ACBDAx4(void);   /* 模式四：按模式三路径跑 4 圈 */

/* 周期任务：真机 50ms 定时中断（编码器采样 + 白区消抖 + LED 时序） */
void xunji_tick_50ms(void);
/* 周期任务：真机 10ms 定时中断（模式二/三白区消抖） */
void xunji_tick_10ms(void);

/* 加权质心巡线核心（bias>0 线偏右右转，<0 左转，=0 无线） */
float xunji_centroid(float gain);
float PID_A(float Encoder, float Target);
float PID_B(float Encoder, float Target);
float PWM_Limit(float IN, float max, float min);
int myabs(int a);

#endif
