/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《MQ-135空气质量传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/mq-135-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef MQ135_STM32_H
#define MQ135_STM32_H

#include <stdint.h>

/* MQ-135 空气质量传感器驱动（stm32 纯驱动薄封装，ADR 0009）：
 * - **ADC 共享组共读**：经母版 ml_adc API 读 ADC1 通道（mq135_init =
 *   adc_init(ADC_1, MQ135_AO_CH)；ADC 通道宏 MQ135_AO_CH 单源在
 *   pin_config.h，默认 ADC_Channel_5 = PA5——**页面原脚**（用户照页面
 *   接线即插即用）；本批 8 件与 flame 共读 PA5（ml_adc 顺序调用无扰）；
 *   同一物理脚只能接一件器件——多件同测需外部分路器/分时切换（mspm0
 *   MEM0 共读同口径）；
 * - 输出电压 → 浓度百分比：percent = value/4095×100（页面
 *   Get_MQ135_Percentage_value 原式——**相对值**，非 ppm 精标；模块上电
 *   需预热（几分钟级）、真实 ppm 需标准气体标定）；
 * - 轮询读取（无 ADC 中断——模块 API 忙等单点实现）；
 * - 5 次快速平均（页面 SAMPLES 30 次累加，mq2/us016 快平均先例改 5 次）；
 * - DO 数字量未声明（页面 Get_MQ135_DO_value（PA1，IPU）演示未用——mspm0
 *   先例「未用不声明」，不落 pins/不落码）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--mq-135-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、页面 ADC 序列收敛 ml_adc、SAMPLES 30→5 快平均、C99 循环声明改
 * uint8_t；页面 L185「酒精值」串台（MQ-3 模板残留）——notes 记录不落码）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值 */
#define MQ135_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，mq2 快平均先例改 5 次） */
#define MQ135_ADC_SAMPLES 5u

/* mq135_init：初始化 ADC1 对应通道（AO 模拟输入——页面 ADC_MQ135_Init 的
 * AIN 配置 + 6 分频 12MHz + 校准流程由 ml_adc 内部完成）。 */
void mq135_init(void);

/* mq135_read_percent：读 AO 电压对应浓度百分比（0-100% 相对值——MQ 系读数
 * 随环境/老化漂移，非 ppm 精标；模块预热后读数才稳定；对氨气/硫化物/苯系/
 * 烟雾灵敏）。 */
float mq135_read_percent(void);

#endif /* MQ135_STM32_H */
