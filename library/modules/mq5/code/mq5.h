#ifndef MQ5_H
#define MQ5_H

#include <stdint.h>

/* MQ-5 液化气/天然气传感器驱动（mspm0 纯驱动切片，ADR 0009）：
 * - **独立 ADC 通道**：经库内 adc 模块 API 读 ADC12_0 MEM5（adc_get(ADC_1,
 *   ADC_Channel_5)，默认 PB24/A0_5，母版 sequence 六通道 endAdd=5）——
 *   与 mq2 的 MEM0 薄封装（adc/us016/mq2 共读同槽）不同：多路气体同选时
 *   各器件物理通道独立、无共读冲突（mq2+mq5 同选 = PA24/PB24 两槽位）；
 * - 输出电压 → 浓度百分比：percent = value/4095×100（页面
 *   Get_MQ5_Percentage_value 原式——**相对值**，非 ppm 精标；模块上电
 *   需预热（几分钟级）、真实 ppm 需标准气体标定）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 SAMPLES 30 次累加，mq2/us016 快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--mq-5-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、DO 数字量阈值未声明——页面 Get_MQ5_DO_value
 * 走 LM393 阈值比较、阈值由模块可调电阻控制）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值 */
#define MQ5_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，mq2 快平均先例改 5 次） */
#define MQ5_ADC_SAMPLES 5u

/* mq5_init：使能 ADC12_0 转换（独立 MEM5 通道轮询——adc_init 即初始化）。 */
void mq5_init(void);

/* mq5_read_percent：读 AO 电压对应浓度百分比（0-100% 相对值——MQ 系读数
 * 随环境/老化漂移，非 ppm 精标；模块预热后读数才稳定；对丁烷/丙烷/甲烷/
 * 天然气灵敏）。 */
float mq5_read_percent(void);

#endif /* MQ5_H */
