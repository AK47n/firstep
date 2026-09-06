/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《人体红外传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/human-body-infrared-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef HUMAN_IR_STM32_H
#define HUMAN_IR_STM32_H

#include <stdint.h>

/* HC-SR501 人体红外感应模块驱动（stm32，纯驱动切片，ADR 0009）：1 × GPIO
 * 输入（内部上拉，页面 IPU），human_ir_read() 返回 1=感应到人体、0=未感应
 * 到。引脚 = pin_config.h 单源 HUMAN_IR_GPIO/HUMAN_IR_PIN（默认 PB7——与
 * pid 灰度 GRAY_D8 默认重叠：人体红外与「巡线灰度」不同框、同选概率最低
 * （刻意避让声光/按键/门禁组合 BUZZER/KEY/SERVO），同选时经引脚绑定消解；
 * 页面默认 PA1 不采用——被 adc ADC_CH1/motor PWM/编码器线占用）。
 * 极性（按模块介绍文字与规格）：人被感应到 = 输出**高电平**（「人进入其
 * 感应范围则输出高电平」+ 规格「电平输出：高3.3V/低0V」；⚠️ 页面函数注释
 * 「0=感应到人体红外」与介绍/规格矛盾——按 HC-SR501 器件标准修正，页面
 * 代码实际也按高=1 实现（L108）；实物低有效改 HUMAN_IR_TRIGGER_LEVEL 0 即可
 * 反相，其余零改动（单点反相宏，TTP224_TOUCH_LEVEL 先例）。
 * 模块特性（页面说明）：上电 ~1 分钟初始化期间间隔输出 0-3 次（初始化期勿
 * 作判定）；可重复/不可重复触发跳线、板载延时与灵敏度旋钮；避免灯光直射
 * 透镜与流动风、双元探头安装方向与人体活动方向平行、<100° 锥角。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--human-body-infrared-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、
 * 页面 Get_HumanIR/GET 宏收敛为 init/read + 极性单宏）。 */

/* 感应判定电平（单点反相宏）：1 = 引脚高 = 感应到（模块介绍/规格，HC-SR501
 * 器件标准——页面注释矛盾按规格修正）；0 = 引脚低 = 感应到（实物反相时改
 * 此宏，其余零改动）。 */
#define HUMAN_IR_TRIGGER_LEVEL 1u

/* human_ir_init：GPIO 输入配置（内部上拉——页面 HumanIR_Init 的
 * GPIO_Mode_IPU 等价，gpio_init 内部使能时钟）。 */
void human_ir_init(void);

/* human_ir_read：读感应状态。返回 1 = 感应到人体、0 = 未感应到（按
 * HUMAN_IR_TRIGGER_LEVEL 极性；电平直读无去抖/无 GPIO 中断——轮询，
 * 页面同为电平直读，骨架侧按需滤波）。 */
uint8_t human_ir_read(void);

#endif /* HUMAN_IR_STM32_H */
