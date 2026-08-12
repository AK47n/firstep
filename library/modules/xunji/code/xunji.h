#ifndef __XUNJI_H_
#define __XUNJI_H_
#include "ti_msp_dl_config.h"
#include <stdint.h>

/* ===== 灰度循迹驱动（mspm0） =====
 * 8 路灰度读取 + 加权质心巡线核心 + 编码器采样读 + 电机速度输出绑定。
 * 纯驱动切片（ADR 0009）：路口计数 / 模式状态机 / 声光时序等决策逻辑不在此
 * 模块——归生成骨架（决策素材可读参考文件库的巡线决策例程）。
 *
 * 硬件映射（母版默认外设布局，实际接线不同改 xunji.c 头部 P1..P8 宏）：
 *   灰度 8 路 → HUIDU_L3/L2/L1/R1/R2/L4/R3/R4（huidu 模块索引序，编译级默认）
 *   电机 → motor 模块（方向 0停1正转2反转；PWM 原始占空比 0~1300）
 *   编码器 → key 模块 counter_1_A/counter_2_A（单沿计数无方向，读后清零）
 * 极性：非零 = 白区。
 */

void xunji_init(void);

/* 灰度 8 路位图：bit0=P1（左外）… bit7=P8（右外），1 = 白区 */
uint8_t xunji_read_gray(void);

/* 加权质心巡线核心：对所有压线传感器做加权平均，输出连续差速值
 * gain: 增益系数，值越大转向越激进；返回正=右转，负=左转，0=未检测到线 */
float xunji_centroid(float gain);

/* 编码器采样读（读后清零）：key 模块中断累加计数，由骨架调度周期采样 */
void xunji_encoder_read(int32_t *left, int32_t *right);

/* 电机速度输出：百分比制（正=前进，负=后退）→ motor 模块原始占空比 0~1300 */
void xunji_set_speed(int left, int right);

#endif
