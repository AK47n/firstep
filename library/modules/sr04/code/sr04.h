/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《SR04超声波测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/sr04-ultrasonic-ranging-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef SR04_H
#define SR04_H

#include <stdint.h>

/* HC-SR04 超声波测距驱动（mspm0，纯驱动切片，ADR 0009）：TRIG 发 10us 触发
 * 脉冲 → ECHO 高电平脉宽计时（CPU 时钟忙等计数，32 周期 = 1us）→ 距离换算 cm。
 * 引脚 = 母版 syscfg 实例：TRIG（输出，默认 PB24——与 STEP_MOTOR RST2 默认
 * 重叠，同选时经引脚绑定消解）/ ECHO（输入，默认 PB8——与 STEP_MOTOR DCY2
 * 同脚）。无定时器依赖（地猛星 SysConfig TIMER 实例仅暴露 TIMG0/6/7/8/12，
 * 已被 motor/pid/ntb_time/servo/step_motor 全占——忙等测宽不占外设）。
 * 时序（HC-SR04 数据手册）：TRIG 高 ≥10us 触发，模块发 8 个 40kHz 声波后
 * ECHO 拉高，回波到达后拉低——脉宽 = 往返时间，距离 = 脉宽(us)/58 (cm)。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--sr04-ultrasonic-ranging-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 printf/main.c 演示、
 * 函数名规范化、引脚宏参数化、延时走 delay 模块、计时滤波保留 5 次平均）。 */

/* 5 次测量平均（立创原版算法）；任一次超时整次返回 0 */
#define SR04_SAMPLE_COUNT 5
#define SR04_TIMEOUT_US 30000u /* 约 5m 量程上限（30ms 回声脉宽 ≈ 5.17m） */

/* sr04_init：初始化（SysConfig 已配引脚，本函数仅置引脚空闲电平）。 */
void sr04_init(void);

/* sr04_get_distance_cm：测一次距离（5 次平均），返回厘米；超时/无回波返回 0。 */
float sr04_get_distance_cm(void);

#endif /* SR04_H */
