/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《土壤湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/soil-moisture-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef SOIL_STM32_H
#define SOIL_STM32_H

#include <stdint.h>

/* 土壤湿度传感器驱动（stm32 纯驱动薄封装，ADR 0009）：
 * - **ADC 共享组共读**：经母版 ml_adc API 读 ADC1 通道（soil_init =
 *   adc_init(ADC_1, SOIL_AO_CH)；ADC 通道宏 SOIL_AO_CH 单源在 pin_config.h，
 *   默认 ADC_Channel_5 = PA5——**页面原脚**（用户照页面接线即插即用）；
 *   本批 8 件与 flame 共读 PA5（ml_adc 顺序调用无扰）；同一物理脚只能接
 *   一件器件——多件同测需外部分路器/分时切换（mspm0 MEM0 共读同口径）；
 *   与 mspm0 默认脚 PA14（板载 LED2+15k 固定衰减）不同——stm32 侧 PA5 无
 *   板载负载问题（notes 澄清）；
 * - 叉子插土壤：水分越足电导越高、AO 电压越大——输出电压 → 湿度百分比为
 *   **正向映射**：percent = value/4095×100（页面 Get_SH_Percentage_value
 *   原式——**相对湿度非绝对值**，与土壤类型/压实度/器件差异有关，页面
 *   说明「模拟量输出更精确」相对 DO 阈值而言）；
 * - 轮询读取（无 ADC 中断——模块 API 忙等单点实现）；
 * - 5 次快速平均（页面 SAMPLES 30 次累加，mq2/us016 快平均先例改 5 次）；
 * - DO 数字量未声明（页面 Get_SH_DO_value（PA1，IPU）main 未用——mspm0
 *   先例「未用不声明」，不落 pins/不落码）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--soil-moisture-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、页面 ADC 序列收敛 ml_adc、SAMPLES 30→5 快平均；页面 L138-140
 * 「Get_Adc_Dma_Value/DMA」函数名残留 + L186「可燃气体」串台——notes 记录
 * 不落码）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值
 * （正向映射：水分越足 ADC 值越大、百分比越高；stm32 默认 PA5 无 mspm0
 * PA14 板载 LED2+15k 固定负载问题） */
#define SOIL_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，mq2 快平均先例改 5 次） */
#define SOIL_ADC_SAMPLES 5u

/* soil_init：初始化 ADC1 对应通道（AO 模拟输入——页面 ADC_SOILHUMIDITY_Init
 * 的 AIN 配置 + 6 分频 12MHz + 校准流程由 ml_adc 内部完成）。 */
void soil_init(void);

/* soil_read_percent：读 AO 电压对应土壤湿度百分比（0-100% 相对值——正向
 * 映射：百分比越高土壤越湿；读数与土壤类型/压实度有关、模拟量输出比 DO
 * 阈值精确；板载蓝色电位器用于灵敏度调节与 DO 阈值）。 */
float soil_read_percent(void);

#endif /* SOIL_STM32_H */
