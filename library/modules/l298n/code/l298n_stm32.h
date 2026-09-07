/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《L298N电机驱动模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/l298n-motor-drive-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef L298N_STM32_H
#define L298N_STM32_H

#include <stdint.h>

/* L298N 大电流电机驱动（stm32 纯驱动切片，ADR 0009）：方向 + 调速形态
 * （页面 AO_Control 原样——IN1/IN2 双通道 PWM：dir=1 → CH1=0/CH2=duty，
 * dir=0 → CH1=duty/CH2=0；**API 与 mspm0 l298n.h 同名同型**：l298n_init /
 * l298n_set_duty(uint32_t) / l298n_set_direction(uint8_t) +
 * L298N_PWM_PERIOD 2000u——mspm0 定稿单路形态，页内 EN/跳线帽 = 范围外
 * （页面规格「5V 使能高电平有效，常态跳线帽接 VCC；PWM 调速时取帽」——
 * 无 EN 代码，跳线帽态使用，notes 记录）；
 * - 独立模块（不并入 motor）：L298N 是大电流双 H 桥（持续 2A、峰值 3A、
 *   压降 ~1.5V、发热大），无编码器脚（无闭环）；与 motor(TB6612：1.2A
 *   轻量双路、带编码器闭环 API) 接线/芯片/场景差异大——适用大电流/重载/
 *   多路电机、无编码器闭环场景（平衡车/推车/闸机/重载底盘）；
 * - 引脚/极性由 pin_config.h 宏与值决定（L298N_IN1/IN2_TIM/CH），模块
 *   代码零引脚字面量；默认 IN1=PA6（TIM3_CH1）/IN2=PA7（TIM3_CH2）=
 *   页面原脚（TIM3 定时器零占用；与 TB6612 motor（TIM2/PA0-1）互替刻意
 *   错开 TIM 与脚；**PA6/PA7 与软 I2C 总线同脚**——L298N×I2C 件同选 =
 *   物理冲突 ⚠（绑定消解）；**TIM 门禁只查用户绑定**——骨架调度模板默认
 *   TIM_3 × 本件默认 TIM_3 属默认×默认不拦（现状口径：骨架用 TIM_3 调度
 *   模板时建议绑 TIM4_CH2/CH3 或改调度模板，见 manifest notes——届时按
 *   年份模板对照）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/
 * control--l298n-motor-drive-module.md（立创 wiki 地阔星移植手册；代码按
 * 模块库规范改写：去 main.c 演示与 printf、AO_Control 按库风格拆分为
 * set_direction + set_duty（内部保留 duty 状态、方向切换重应用——页面
 * 「speed 范围 0~per-1」语义）、引脚宏参数化）。 */

#define L298N_PWM_PERIOD 2000u /* 占空比上限参数（与 mspm0 l298n.h 同名同型） */
#define L298N_PWM_FREQ   500   /* PWM 频率：1MHz 计数 / 2000 步骤 = 500Hz
                                * （页面 1kHz/1000 步骤与 mspm0 16kHz/2000
                                * 步骤差异——本件照 mspm0 定稿 2000 步骤） */

/* l298n_init：双 PWM 通道初始化（页面 L298N_Init(72,1000) 原式换算——
 * pwm_init 每通道同频）+ 双通道 0 + 计数器启动（页面 AO_Control 前须启动
 * PWM 计数器）。 */
void l298n_init(void);

/* l298n_set_duty：调速（页面 AO_Control 的 speed 语义，0~per-1）——限幅到
 * L298N_PWM_PERIOD-1，按当前方向应用（dir=1 → CH1=0/CH2=duty、dir=0 →
 * CH1=duty/CH2=0；页面原样）。 */
void l298n_set_duty(uint32_t duty);

/* l298n_set_direction：方向（页面 dir 语义 1 正转 / 0 反转）——切换方向
 * 时按当前 duty 重应用（CH1/CH2 互换）。 */
void l298n_set_direction(uint8_t dir);

#endif /* L298N_STM32_H */
