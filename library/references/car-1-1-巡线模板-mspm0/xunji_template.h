/**
 * xunji_template.h — 小车巡线逻辑可复用模板（头文件）
 */

#ifndef __XUNJI_TEMPLATE_H__
#define __XUNJI_TEMPLATE_H__

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================
// 硬件抽象接口（需要在平台层实现）
// ============================================================

/**
 * 读取第 index 个灰度传感器
 * @param index  0 ~ (SENSOR_COUNT-1)，对应 P1 ~ PN
 * @return       true = 检测到黑线, false = 白色地面
 */
bool hal_read_grayscale(uint8_t index);

/**
 * 设置左/右电机
 * @param pwm  >0 前进, <0 后退, |pwm| = 占空比(0~100)
 */
void hal_set_motor_left(int16_t pwm);
void hal_set_motor_right(int16_t pwm);

/**
 * 控制 LED 指示灯
 */
void hal_set_led(bool on);

/**
 * 使能/禁能电机驱动芯片（STBY）
 */
void hal_motor_enable(bool enable);

/**
 * 获取陀螺仪偏航角
 * @return Yaw 角度，-180° ~ +180°
 */
float hal_get_yaw(void);

// ============================================================
// 巡线核心算法
// ============================================================

/**
 * 加权质心巡线
 * @param gain  增益系数（推荐 3.0 ~ 7.0）
 * @return      bias: >0 右转, <0 左转, =0 无线
 */
float xunji_centroid(float gain);

// ============================================================
// 模式控制函数
// ============================================================

void Control_AB(void);         // 模式0: 纯陀螺仪直行
void Control_ABCDA(void);      // 模式1: 单圈巡线（含白区掉头）
void Control_ACBDA(void);      // 模式2: 含固定角度掉头
void Control_ACBDAx4(void);    // 模式3: 模式2的四圈版本

// ============================================================
// 中断回调（需要在对应的 ISR 中调用）
// ============================================================

/**
 * 50ms 定时中断回调 — 编码器采样、白区防抖、LED控制
 */
void xunji_timer_50ms_callback(void);

/**
 * 10ms 定时中断回调 — 模式2/3的白区确认延时
 */
void xunji_timer_10ms_callback(void);

/**
 * 编码器 A/B 相中断回调 — 正交解码
 */
void xunji_encoder_callback(uint8_t channel, bool phase_a_rise, bool phase_b_level);

/**
 * 陀螺仪数据更新（由UART中断调用）
 */
void xunji_update_yaw(float new_yaw);

/**
 * 状态重置（切换模式或重新开始时调用）
 */
void xunji_reset_state(void);

#ifdef __cplusplus
}
#endif

#endif /* __XUNJI_TEMPLATE_H__ */
