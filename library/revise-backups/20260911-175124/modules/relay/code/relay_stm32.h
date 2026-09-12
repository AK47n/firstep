/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《继电器模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/relay-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef RELAY_STM32_H
#define RELAY_STM32_H

#include <stdint.h>

/* 1 路 5V 继电器模块驱动（stm32，纯驱动切片，ADR 0009）：1 × GPIO 输出
 * （光耦隔离/低电平吸合——页面原理：IN1 输出低电平 → 光耦 1/2 脚导通 →
 * 4/3 脚导通 → 三极管基极得电 → 线圈得电 → 触点由常闭吸合到常开，低压
 * 控制高压）。relay_set(1)=吸合（导通）/relay_set(0)=断开；relay_init()
 * 初始断开。
 * ⚠️ 页面甄别：整页为 **F4 口径**（stm32f4xx.h + RCC_AHB1PeriphClockCmd +
 * GPIO_Mode_OUT/OType_PP/PuPd_UP/Speed_100MHz），与页面标题 F103 矛盾——
 * 按 F1 换算表逐行翻译（见 relay_stm32.c 注释 + manifest notes）。
 * 引脚 = pin_config.h 单源 RELAY_GPIO/RELAY_PIN（默认 PB4——与 motor 编码器
 * 方向输入 MOTOR_A_ENC_DIR（pin_config.h）默认重叠：继电器与「带编码器
 * 闭环的电机控制」不同框、同选概率最低（刻意不叠声光/执行件 LED/BUZZER/
 * 电机 PWM/方向——继电器+蜂鸣报警/电灯控制为常见组合），同选时经引脚绑定
 * 消解；PB4 非 PWM/ADC 主用脚，推挽输出无扰）。
 * 极性归一化（本件拍板）：API 语义 1=吸合/0=断开；页面 Set_Relay_Switch
 * 0=吸合/1=断开（页面函数注释「0继电器吸合 1继电器断开」）——对照：
 * Set_Relay_Switch(s) ≡ relay_set(1-s)。实物高电平吸合改 RELAY_ON_LEVEL
 * 为 1 即可，其余零改动（单点极性宏，TTP224_TOUCH_LEVEL 先例）。
 * 模块特性（页面说明）：5V 工作、光耦隔离保护 MCU 引脚、三极管驱动、
 * 4Pin 2.54mm 排针、可控 250V/10A AC 与 30V/10A DC（页面「可达30V,10A」
 * 为直流笔误）；继电器为感性负载——开关瞬态反电动势与触点电弧注意事项
 * （线圈侧建议续流、触点侧外接负载，notes 记录，不落码）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/control--relay-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、极性归一化单宏、F4→F1 换算）。 */

/* 吸合电平（单点极性宏）：0 = 引脚低 = 吸合（页面模块「低电平吸合」，默认
 * ——与页面原理 IN1 低电平吸合一致）；1 = 引脚高 = 吸合（实物高电平吸合时
 * 改此宏，其余零改动）。 */
#define RELAY_ON_LEVEL 0u

/* relay_init：初始化继电器（推挽输出配置 + 初始断开）——上电后继电器处于
 * 断开态（页面演示「上电即吸合」为演示语义，归生成骨架控制）。 */
void relay_init(void);

/* relay_set：设置继电器状态。state=1 = 吸合（导通，常开触点闭合接负载）、
 * state=0 = 断开（释放）。页面编码对照：Set_Relay_Switch(s) ≡
 * relay_set(1-s)（页面 0=吸合/1=断开，本件归一化为 1=吸合/0=断开；吸合
 * 电平由 RELAY_ON_LEVEL 承载——默认 0u = 引脚低=吸合）。 */
void relay_set(uint8_t state);

#endif /* RELAY_STM32_H */
