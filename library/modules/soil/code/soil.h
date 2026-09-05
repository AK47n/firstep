#ifndef SOIL_H
#define SOIL_H

#include <stdint.h>

/* 土壤湿度传感器驱动（mspm0 纯驱动切片，ADR 0009）：
 * - **独立 ADC 通道**：经库内 adc 模块 API 读 ADC12_0 MEM7（adc_get(ADC_1,
 *   ADC_Channel_7)，默认 PA14/A0_12，母版 sequence 八通道 endAdd=7）——
 *   **MEM 槽位已满（8/8）**：后续 ADC 类件（photoresistance/rain/gp2y1014au/
 *   s12sd/ms1100）一律薄封装共读 MEM0 模式（mq2/us016 先例——多件同选
 *   同读一物理通道、一次转换一次读、采样节奏按用途自协调）；
 * - 叉子插土壤：水分越足电导越高、AO 电压越大——输出电压 → 湿度百分比为
 *   **正向映射**：percent = value/4095×100（页面 Get_SH_Percentage_value
 *   原式——**相对湿度非绝对值**，与土壤类型/压实度/器件差异有关，页面
 *   说明「模拟量输出更精确」相对 DO 阈值而言）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 Get_Adc_Value SAMPLES 30 次累加，mq2/us016
 *   快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--soil-moisture-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、DO 数字量阈值未声明——页面 Get_SH_DO_value
 * 走 LM393 阈值比较、阈值由模块板载蓝色电位器控制）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值
 * （正向映射：水分越足 ADC 值越大、百分比越高；注意默认脚 PA14 板载
 * LED2+15k 固定负载会使读数系统偏小——单调性保留、阈值/趋势判断可用） */
#define SOIL_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，mq2 快平均先例改 5 次） */
#define SOIL_ADC_SAMPLES 5u

/* soil_init：使能 ADC12_0 转换（独立 MEM7 通道轮询——adc_init 即初始化）。 */
void soil_init(void);

/* soil_read_percent：读 AO 电压对应土壤湿度百分比（0-100% 相对值——正向
 * 映射：百分比越高土壤越湿；读数与土壤类型/压实度有关、模拟量输出比 DO
 * 阈值精确；板载蓝色电位器用于灵敏度调节与 DO 阈值。 */
float soil_read_percent(void);

#endif /* SOIL_H */
