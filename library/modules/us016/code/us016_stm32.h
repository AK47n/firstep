/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《US-016超声波测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/us-016-ultrasonic-ranging-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef US016_STM32_H
#define US016_STM32_H

/* US-016 模拟量超声波测距驱动（stm32 纯驱动薄封装，ADR 0009）：
 * - **ADC 共享组共读**：经母版 ml_adc API 读 ADC1 通道（us016_init =
 *   adc_init(ADC_1, US016_AO_CH)；ADC 通道宏 US016_AO_CH 单源在 pin_config.h，
 *   默认 ADC_Channel_5 = PA5——页面原脚即共读点：用户照页面接线即插即用）；
 *   **与 ir_distance 互替件同脚**（两测距件同一物理脚只能接一件——互替同脚
 *   先例，二选一接入无需另消解；同选时经绑定其一换 PA0/PA1）；与 flame/
 *   批次 5/6 件共读 PA5（ml_adc 的 adc_get 每次先写 SQR3 选通道再触发转换，
 *   顺序调用互不干扰）；同一物理脚只能接一件器件——多件同测需外部分路器/
 *   分时切换（mspm0 MEM0 共读同口径）；
 * - 电压 → 距离：L = (A×3072/4096)×(Vref/Vcc) mm（Range 悬空/高 = 3m 量程，
 *   默认；Range 低 = 1m 量程系数 0.25，编译期宏 US016_RANGE_1M——照 mspm0
 *   us016.h L17-19 双量程口径；页面正文「3096」与代码「3072」不一，按代码
 *   0.75 定稿，notes 记录）；
 * - 轮询读取（无 ADC 中断——ml_adc 忙等单点实现）；
 * - 5 次快速平均（页面 50 次 × delay_ms(10) ≈ 500ms 阻塞采样太慢——mspm0/
 *   us016 快平均先例；出参 cm 对齐 mspm0 us016_read_distance_cm）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--us-016-ultrasonic-ranging-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、页面 ADC 序列收敛 ml_adc、50 次采样改 5 次快平均）。 */

/* 0 = 3m 量程（Range 悬空/高，系数 A×0.75mm）；1 = 1m 量程（Range 低，系数
 * A×0.25mm）；对应手册 #define RANGE（照 mspm0 us016.h L17-19） */
#define US016_RANGE_1M 0

/* 换算系数 Vref/Vcc：L = (A×3072/4096)×(Vref/Vcc) mm——Vref = ADC 参考电压、
 * Vcc = 模块供电电压。默认 Vref=Vcc=3.3V（系数 1）；模块改 5V 供电时把
 * US016_VCC_V 改 5.0f，系统误差即消除（照 mspm0 us016.h L21-25）。 */
#define US016_VREF_V 3.3f
#define US016_VCC_V 3.3f

/* 快速平均采样次数（页面 50 次 × delay_ms(10) ≈ 500ms 阻塞采样——mspm0/
 * us016 快平均先例改 5 次；真机行为差异 notes） */
#define US016_ADC_SAMPLES 5

/* us016_init：初始化 ADC1 对应通道（AO 模拟输入——页面 US016_GPIO_Init 的
 * AIN 配置 + APB2 时钟 + 6 分频 12MHz + 校准流程由 ml_adc 内部完成）。 */
void us016_init(void);

/* us016_read_distance_cm：距离换算结果（cm——页面 main L254 /10 出 cm 归入
 * API 出参）：3m 量程 0-307.2cm / 1m 量程 0-102.4cm；内部 5 次快速平均
 * （页面 50 次 × 10ms 阻塞采样改快平均，改动见 manifest notes）。 */
float us016_read_distance_cm(void);

#endif /* US016_STM32_H */
