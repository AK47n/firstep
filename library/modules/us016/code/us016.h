#ifndef US016_H
#define US016_H

/* US-016 模拟量超声波测距驱动（mspm0 纯驱动，ADR 0009）：
 * - 薄封装：依赖库内 adc 模块读 ADC12_0 MEM0（adc_get(ADC_1, ADC_Channel_0)），
 *   不新开 ADC 通道——us016 与 adc 模块共享 MEM0 槽位（默认 PA24/A0_3）；
 * - 电压 → 距离：L = (A×3072/4096)×(Vref/Vcc) mm（Range 悬空/高 = 3m 量程，
 *   默认；Range 低 = 1m 量程系数 0.25，编译期宏 US016_RANGE_1M）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）。 */

void us016_init(void);
/* 距离换算结果（cm），3m 量程 0-307.2cm / 1m 量程 0-102.4cm；
 * 内部 5 次快速平均（立创原版 50 次 × 10ms 太慢，改动见 manifest notes）。 */
float us016_read_distance_cm(void);

#endif /* US016_H */
