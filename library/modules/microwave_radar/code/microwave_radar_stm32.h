/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《微波多普勒无线雷达传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/microwave-doppler-radar-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef MICROWAVE_RADAR_STM32_H
#define MICROWAVE_RADAR_STM32_H

#include <stdint.h>

/* HB100 微波多普勒雷达模块驱动（stm32，纯驱动切片，ADR 0009）：1 × GPIO
 * 输入（内部上拉，页面 IPU），microwave_radar_read() 返回 1=检测到移动、
 * 0=无移动。引脚 = pin_config.h 单源 MICROWAVE_GPIO/MICROWAVE_PIN（默认
 * PA4——与 motor 编码器 B 相 EXTI（MOTOR_B_ENC EXTI_PA4）默认重叠：微波
 * 雷达与「带编码器闭环的电机控制」不同框、同选概率最低（刻意避让声光/
 * 门禁/传感站组合件），同选时经引脚绑定消解；本件轮询不注册 EXTI，与编码
 * 器线共享正交（异口同线此时不冲突）；页面默认 PA1 不采用——叠 adc
 * ADC_CH1 + MOTOR_B_PWM 常备件）。
 * 极性（按页面，自一致）：页面函数注释 + main 演示均按「检测到物体移动 =
 * OUT 低电平」（判移动按 OUT 输入为 0；0=检测到、1=未检测到）
 * ——默认沿用页面；正文未声明极性，HB100 带底板的 OUTPUT 极性因底板而异
 * （未上板），实物输出反相时把 MICROWAVE_TRIGGER_LEVEL 改为 1 即可反相，
 * 其余零改动（单点反相宏，TTP224_TOUCH_LEVEL 先例）。
 * 模块特性（页面说明）：多普勒原理检测**物体运动**（不局限于人体、不受
 * 环境温度影响、探测距离 2-16m 连续可调、5V±0.25V 供电、30-50mA）；页面
 * main 演示的开/关门时序逻辑（flag/time、2000ms 关门）归生成骨架
 * （ADR 0009——模块只出 init/read）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--microwave-doppler-radar-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf/演示
 * 时序、页面 OUTPIN_Scanf/OUT_IN 宏收敛为 init/read + 极性单宏、页面宏名
 * 无前缀（RCC_OUT/PORT_OUT/GPIO_OUT/OUT_IN）统一 MICROWAVE_ 前缀）。 */

/* 检测判定电平（单点反相宏）：0 = 引脚低 = 检测到移动（页面注释+演示，
 * 页面原样）；1 = 引脚高 = 检测到移动（实物输出反相时改此宏，其余零改动）。 */
#define MICROWAVE_TRIGGER_LEVEL 0u

/* microwave_radar_init：GPIO 输入配置（内部上拉——页面 MH100X_GPIO_Init 的
 * GPIO_Mode_IPU 等价，gpio_init 内部使能时钟；页面 Speed_50MHz 对输入模式
 * 冗余，不保留）。 */
void microwave_radar_init(void);

/* microwave_radar_read：读检测状态。返回 1 = 检测到物体移动、0 = 无移动
 * （按 MICROWAVE_TRIGGER_LEVEL 极性；电平直读无去抖/无 GPIO 中断——轮询，
 * 页面同为电平直读，骨架侧按需滤波；注意只对运动物体敏感，静止人体
 * 不触发）。 */
uint8_t microwave_radar_read(void);

#endif /* MICROWAVE_RADAR_STM32_H */
