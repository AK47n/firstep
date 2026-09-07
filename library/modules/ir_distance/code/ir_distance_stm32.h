/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《红外测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/Infrared-distance-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef IR_DISTANCE_STM32_H
#define IR_DISTANCE_STM32_H

/* GP2Y0A02YK0F 红外测距驱动（stm32 纯驱动薄封装，ADR 0009）：
 * - **ADC 共享组共读**：经母版 ml_adc API 读 ADC1 通道（ir_distance_init =
 *   adc_init(ADC_1, IR_DISTANCE_AO_CH)；ADC 通道宏 IR_DISTANCE_AO_CH 单源在
 *   pin_config.h，默认 ADC_Channel_5 = PA5——页面原脚即共读点：用户照页面
 *   接线即插即用）；**与 us016 互替件同脚**（两测距件同一物理脚只能接一件
 *   ——互替同脚先例；同选时经绑定其一换 PA0/PA1）；与 flame/批次 5/6 件
 *   共读 PA5（ml_adc 顺序调用无扰）；
 * - 换算：V = raw/4095×IR_DIST_VREF_V（**页面硬编码 3.5V、mspm0 已宏化 3.3**
 *   ——3.3V 供电下页面换算系统偏低约 6%，照 mspm0 宏化修正），
 *   Distance = 60.374×V^(-1.16)（GP2Y0A02YK0F 官方公式，20-150cm 段）；
 *   **<15cm 电压跌落非线性区**（≈远距读数假象）——安装位置须避开、不保证
 *   该段精度（随手册警告）；
 * - 轮询读取（无 ADC 中断——ml_adc 忙等单点实现）；10 次快速平均（手册
 *   Get_Adc_Value(10) 原值——页面 30 次连续累加改 10 次，mspm0 同口径）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--Infrared-distance-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、页面 ADC 序列收敛 ml_adc、3.5V 常数宏化——页面 L44「下图曲线图」
 * 实为 0 图：无查表，按公式）。 */

/* 采样平均次数（手册 Get_Adc_Value(10) 原值；页面 30 次连续无延时累加——
 * mspm0 沿 10 次，非 5 次快平均口径——notes 记录） */
#define IR_DIST_ADC_SAMPLES 10

/* 12bit 满量程（页面 4095 原值） */
#define IR_DIST_ADC_MAX 4095

/* ADC 参考电压（= 模块供电 Vcc 时换算最准）：页面硬编码 3.5V——F103 供电
 * 3.3V 下页面换算系统偏低约 6%，照 mspm0 宏化 3.3（IR_DIST_VREF_V 一处改）。 */
#define IR_DIST_VREF_V 3.3f

/* ir_distance_init：初始化 ADC1 对应通道（AO 模拟输入——页面 IRdistance_
 * GPIO_Init 的 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 校准流程由 ml_adc
 * 内部完成）。 */
void ir_distance_init(void);

/* ir_distance_read_distance_cm：距离换算结果（cm——GP2Y0A02YK0F 公式段
 * 20-150cm）；0.0f = 异常（采样为 0：未接传感器/引脚悬空——避免
 * pow(0,-1.16) 溢出，与 mspm0 ir_distance_read_distance_cm 同口径）；
 * <15cm 电压跌落非线性区不保证（随手册警告）。 */
float ir_distance_read_distance_cm(void);

#endif /* IR_DISTANCE_STM32_H */
