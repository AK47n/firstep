/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《US-016超声波测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/us-016-ultrasonic-ranging-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef US016_H
#define US016_H

/* US-016 模拟量超声波测距驱动（mspm0 纯驱动，ADR 0009）：
 * - 薄封装：依赖库内 adc 模块读 ADC12_0 MEM0（adc_get(ADC_1, ADC_Channel_0)），
 *   不新开 ADC 通道——us016 与 adc 模块共享 MEM0 槽位（默认 PA24/A0_3）；
 * - 电压 → 距离：L = (A×3072/4096)×(Vref/Vcc) mm（Range 悬空/高 = 3m 量程，
 *   默认；Range 低 = 1m 量程系数 0.25，编译期宏 US016_RANGE_1M）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）。 */

/* 0 = 3m 量程（Range 悬空/高，系数 A×0.75mm）；1 = 1m 量程（Range 低，系数
 * A×0.25mm）；对应手册 #define RANGE */
#define US016_RANGE_1M 0

/* 换算系数 Vref/Vcc：L = (A×3072/4096)×(Vref/Vcc) mm——Vref = ADC 参考电压、
 * Vcc = 模块供电电压。手册默认 Vref=Vcc=3.3V（系数 1）；模块改 5V 供电时
 * 把 US016_VCC_V 改 5.0f，系统误差即消除（真机以万用表实测为准）。 */
#define US016_VREF_V 3.3f
#define US016_VCC_V 3.3f

void us016_init(void);
/* 距离换算结果（cm），3m 量程 0-307.2cm / 1m 量程 0-102.4cm；
 * 内部 5 次快速平均（立创原版 50 次 × 10ms 太慢，改动见 manifest notes）。 */
float us016_read_distance_cm(void);

#endif /* US016_H */
