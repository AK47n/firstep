/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《双轴按键摇杆模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/two-axis-keystroke-rocker-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef JOYSTICK_STM32_H
#define JOYSTICK_STM32_H

#include <stdint.h>

/* 双轴摇杆按键驱动（stm32 纯驱动，ADR 0009）：
 * - X/Y 两轴：经母版 ml_adc API 读 ADC1 两通道（引脚/通道宏单源在
 *   pin_config.h：JOYSTICK_X_CH = ADC_Channel_1（默认 PA1）、JOYSTICK_Y_CH =
 *   ADC_Channel_0（默认 PA0）——与 adc 模块 ADC_CH1/CH0 **ADC 共享组**
 *   （mspm0 MEM1/2 与 adc 模块共享实例同构；ml_adc 的 adc_get 每次先写
 *   SQR3 选通道，顺序调用互不干扰）；轮询读取 + 4 次快速平均，12bit 原始
 *   值（0-4095），percent 版按 4095 归一 0-100%（整数运算）；
 * - SW 按键：JOYSTICK_SW 上拉输入（默认 PA10——叠 DIGIT/COORD/UWB UART
 *   RX：摇杆与视觉/数传链路不同框、同选概率最低——mspm0 SW=PA9 同款推理，
 *   同选经引脚绑定消解），按下接地低电平。
 * - 页面缺陷/修正（notes 记录）：页面每次读轴 30 × delay_ms(2) ≈ 60ms +
 *   2 次 ADC 校准无超时 → 4 次快平均（mspm0 批 1 口径）；L149 注释函数名
 *   「Get_MQ2_Percentage_value」MQ2 模板串台——notes 记录不落码。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/control--two-axis-keystroke-rocker-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、页面 ADC 序列收敛 ml_adc、30×2ms 采样改 4 次快平均、SW 极性
 * 宏化——mspm0 版同名 API 全对齐）。 */

/* 12bit 满量程（页面 4095.0f 原值） */
#define JOYSTICK_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 × delay_ms(2) ≈ 60ms/轴太慢——mspm0
 * 批 1 改 4 次快平均口径；无采样延时——ml_adc 忙等单点实现） */
#define JOYSTICK_ADC_SAMPLES 4u

/* SW 按下电平（单点反相宏，照 mspm0 joystick.h L24 同名义）：0 = 引脚低 =
 * 按下（页面原样——上拉输入低有效） */
#define JOYSTICK_SW_PRESSED_LEVEL 0

/* joystick_init：初始化 ADC1 两个通道（X/Y AO 模拟输入——页面 ADC_Joystick_
 * Init 的 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 校准流程由 ml_adc 内部完成；
 * 逐通道调用 adc_init（每次含校准——启动时一次，行为正确））。 */
void joystick_init(void);

/* joystick_read_x：X 轴 12bit 原始值（0-4095；照 mspm0 joystick_read_x 同名
 * 同型 joystick.h L27——页面 Get_Joystick_Percentage_value 底层换算前值）。 */
uint16_t joystick_read_x(void);

/* joystick_read_y：Y 轴 12bit 原始值（0-4095，X 轴同型）。 */
uint16_t joystick_read_y(void);

/* joystick_read_x_percent：X 轴 0-100%（整数——照 mspm0 同名同型
 * joystick.h L29：((uint32_t)raw×100)/4095；页面 ×100.f 浮点式归一整数）。 */
uint16_t joystick_read_x_percent(void);

/* joystick_read_y_percent：Y 轴 0-100%（X 轴同型）。 */
uint16_t joystick_read_y_percent(void);

/* joystick_read_sw：1=按下、0=松开（上拉输入低有效——极性宏
 * JOYSTICK_SW_PRESSED_LEVEL 一处反相；页面 Get_SW_state 0=按下语义归一）。 */
uint8_t joystick_read_sw(void);

#endif /* JOYSTICK_STM32_H */
