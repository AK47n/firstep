#ifndef PHOTORESISTANCE_H
#define PHOTORESISTANCE_H

#include <stdint.h>

/* 光敏电阻光照传感器驱动（mspm0 纯驱动薄封装，ADR 0009）：
 * - 薄封装：依赖库内 adc 模块读 ADC12_0 MEM0（adc_get(ADC_1, ADC_Channel_0)），
 *   不新开 ADC 通道——与 adc/us016/mq2 共享 MEM0 槽位（默认 PA24/A0_3）；
 * - 分压电压 → 亮度百分比：percent = (1 − value/4095)×100（页面原式——
 *   **反向映射**：页面备注「最亮 100 最暗 0」——光越强阻值越小、ADC 值越小、
 *   百分比越高；相对强度非绝对值，非线性需标定）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 10 次累加，按 us016 快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--photoresistance-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、DO 数字量阈值未声明——页面 Get_DO_In 仅宏未使用）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值 */
#define PHOTORESISTANCE_ADC_MAX 4095u

/* 快速平均采样次数（页面 Get_Adc_Value(10) 累加，us016 快平均先例改 5 次） */
#define PHOTORESISTANCE_ADC_SAMPLES 5u

/* photoresistance_init：使能 ADC12_0 转换（薄封装——adc_init 即 MEM0 轮询初始化）。 */
void photoresistance_init(void);

/* photoresistance_read_percent：读 AO 分压对应的亮度百分比（0-100% 相对值，
 * 100 = 最亮、0 = 最暗——页面备注语义；光敏电阻非线性，仅适合作相对光强/
 * 阈值判断，lx 级标定需标准照度源；光照变化时留采样间隔（器件响应非瞬态））。 */
float photoresistance_read_percent(void);

#endif /* PHOTORESISTANCE_H */
