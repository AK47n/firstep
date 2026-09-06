/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《光敏电阻光照传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/photoresistance-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef PHOTORESISTANCE_STM32_H
#define PHOTORESISTANCE_STM32_H

#include <stdint.h>

/* 光敏电阻光照传感器驱动（stm32 纯驱动薄封装，ADR 0009）：
 * - **ADC 共享组共读**：经母版 ml_adc API 读 ADC1 通道（photoresistance_init =
 *   adc_init(ADC_1, PHOTORESISTANCE_AO_CH)；ADC 通道宏
 *   PHOTORESISTANCE_AO_CH 单源在 pin_config.h，默认 ADC_Channel_5 = PA5
 *   ——**页面原脚**（用户照页面接线即插即用）；本批 8 件与 flame 共读 PA5
 *   （ml_adc 顺序调用无扰）；同一物理脚只能接一件器件——多件同测需外部
 *   分路器/分时切换（mspm0 MEM0 共读同口径）；
 * - 分压电压 → 亮度百分比：percent = (1 − value/4095)×100（页面原式——
 *   **反向映射**：页面备注「最亮 100 最暗 0」——光越强阻值越小、ADC 值越
 *   小、百分比越高；相对强度非绝对值，非线性需标定；**本批唯一反向自洽页
 *   ——与 rain 的正向修正对仗，勿改反**）；
 * - 轮询读取（无 ADC 中断——模块 API 忙等单点实现）；
 * - 5 次快速平均（页面 Get_Adc_Value(10) 累加，us016 快平均先例改 5 次）；
 * - DO 数字量未声明（页面 Get_DO_In（PA2，IPU）+ GET_DO_IN 宏 main 未用
 *   ——mspm0 先例「未用不声明」，不落 pins/不落码）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--photoresistance-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、页面 ADC 序列收敛 ml_adc、SAMPLES 10→5 快平均、页面 `stdio.h`
 * 残余 include 剔除）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值
 * （反向映射：100 = 最亮、0 = 最暗——页面备注语义，自洽保留） */
#define PHOTORESISTANCE_ADC_MAX 4095u

/* 快速平均采样次数（页面 Get_Adc_Value(10) 累加，us016 快平均先例改 5 次） */
#define PHOTORESISTANCE_ADC_SAMPLES 5u

/* photoresistance_init：初始化 ADC1 对应通道（AO 模拟输入——页面
 * Illume_GPIO_Init 的 AIN 配置 + 6 分频 12MHz + 校准流程由 ml_adc 内部完成）。 */
void photoresistance_init(void);

/* photoresistance_read_percent：读 AO 分压对应的亮度百分比（0-100% 相对值，
 * 100 = 最亮、0 = 最暗——页面备注语义；光敏电阻非线性，仅适合作相对光强/
 * 阈值判断，lx 级标定需标准照度源；光照变化时留采样间隔（器件响应非瞬态））。 */
float photoresistance_read_percent(void);

#endif /* PHOTORESISTANCE_STM32_H */
