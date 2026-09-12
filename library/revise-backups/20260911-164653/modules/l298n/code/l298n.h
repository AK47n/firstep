/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《L298N电机驱动模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/control/l298n-motor-drive-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef L298N_H
#define L298N_H

#include "ti_msp_dl_config.h"
#include <stdint.h>

/* L298N 大电流电机驱动（mspm0，纯驱动切片，ADR 0009）：方向 + 调速形态
 * （页面 AO_Control 原样——IN1/IN2 双通道 PWM：dir=1 → C0=0/C1=duty，
 * dir=0 → C0=duty/C1=0）+ EN 使能（三脚一组 IN1/IN2/EN，EN 高有效）。
 * 独立模块（不并入 motor）：L298N 是大电流双 H 桥（持续 2A、峰值 3A、
 * 压降 ~1.5V、发热大），无编码器脚（无闭环）；与 motor(TB6612：1.2A
 * 轻量双路、带编码器闭环 API）接线/芯片/场景差异大——适用大电流/重载/
 * 多路电机、无编码器闭环场景（平衡车/推车/闸机/重载底盘）。
 * 引脚 = 母版 syscfg：L298N_PWM（TIMG12，C0=PA14——与 DCC_100_PWM2
 * （step_motor 步进脉冲）同外设默认：L298N 与步进驱动互替、同选概率最低，
 * 同选时经引脚绑定换实例消解；C1=PB24——同上）+ L298N（EN 输出，
 * 默认 PA27——与 HUIDU R2/ADC12_0 adcPin0/TTP224 OUT4 重叠，同选时经引脚
 * 绑定消解；l298n_init 置高 = 使能（页面「5V 使能高电平有效，常态跳线帽
 * 接 VCC；PWM 调速时取下跳线帽、使能接 GPIO」）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/control--l298n-motor-drive-module.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main.c 演示与
 * printf、AO_Control 按库风格拆分为 set_direction + set_duty（内部保留
 * duty 状态、方向切换重应用——页面「speed 范围 0~per-1」语义）、页面
 * DL_TimerG_setCaptureCompareValue 按 motor.c 先例用
 * DL_Timer_setCaptureCompareValue（SDK 2.11 同义 API——motor 编译实测））。
 * 单路范围：页面仅实现 A 端口（IN1/IN2，「IN3/IN4 内容类似」），B 端口
 * （IN3/IN4/ENB）同构扩展留后续/多实例机制。 */

#define L298N_PWM_PERIOD 2000u /* 对应母版 L298N_PWM.timerCount（0..1999） */

/* l298n_init：EN 使能置高（页面「5V 使能高电平有效」——取跳线帽后由 GPIO
 * 驱动）+ 双通道 0 + 计数器启动（页面 AO_Control 前须启动 PWM 计数器）。 */
void l298n_init(void);

/* l298n_set_duty：调速（页面 AO_Control 的 speed 语义，0~per-1）——限幅到
 * L298N_PWM_PERIOD-1，按当前方向应用（dir=1 → C0=0/C1=duty、dir=0 →
 * C0=duty/C1=0；页面原样）。 */
void l298n_set_duty(uint32_t duty);

/* l298n_set_direction：方向（页面 dir 语义 1 正转 / 0 反转）——切换方向
 * 时按当前 duty 重应用（C0/C1 互换）。 */
void l298n_set_direction(uint8_t dir);

#endif /* L298N_H */
