#ifndef MQ2_H
#define MQ2_H

#include <stdint.h>

/* MQ-2 烟雾/可燃气体检测传感器驱动（mspm0 纯驱动薄封装，ADR 0009）：
 * - 薄封装：依赖库内 adc 模块读 ADC12_0 MEM0（adc_get(ADC_1, ADC_Channel_0)），
 *   不新开 ADC 通道——mq2 与 adc/us016 共享 MEM0 槽位（默认 PA24/A0_3）；
 * - 输出电压 → 浓度百分比：percent = value/4095×100（页面原式——**相对值**，
 *   非 ppm 精标；模块上电需预热、真实 ppm 需标准气体标定）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 30 次累加，按 us016 快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--mq-2-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、DO 数字量阈值未声明——页面仅 GET_DO 宏未使用）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值 */
#define MQ2_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，us016 快平均先例改 5 次） */
#define MQ2_ADC_SAMPLES 5u

/* mq2_init：使能 ADC12_0 转换（薄封装——adc_init 即 MEM0 轮询初始化）。 */
void mq2_init(void);

/* mq2_read_percent：读 AO 电压对应浓度百分比（0-100% 相对值——MQ 系读数
 * 随环境/老化漂移，非 ppm 精标；模块预热后读数才稳定）。 */
float mq2_read_percent(void);

#endif /* MQ2_H */
