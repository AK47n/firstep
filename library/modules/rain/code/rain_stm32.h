/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《雨滴传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/rain-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef RAIN_STM32_H
#define RAIN_STM32_H

#include <stdint.h>

/* 雨滴传感器驱动（stm32 纯驱动薄封装，ADR 0009）：
 * - **ADC 共享组共读**：经母版 ml_adc API 读 ADC1 通道（rain_init =
 *   adc_init(ADC_1, RAIN_AO_CH)；ADC 通道宏 RAIN_AO_CH 单源在 pin_config.h，
 *   默认 ADC_Channel_5 = PA5——**页面原脚**（用户照页面接线即插即用）；
 *   本批 8 件与 flame 共读 PA5（ml_adc 顺序调用无扰）；同一物理脚只能接
 *   一件器件——多件同测需外部分路器/分时切换（mspm0 MEM0 共读同口径）；
 * - 分压电压 → 雨量百分比：percent = value/4095×100（**正向映射**——雨越
 *   大百分比越高；页面原式为 (1 − value/4095)×100，与页面正文「雨水越大，
 *   电阻值越小，模拟值转化为的数字值越大」矛盾（照原式雨越大百分比反而越
 *   低），按正文取证修正为正向映射——见 notes；**反向式守卫：percent 公式
 *   不得出现 `1.0f - `**，与 photoresistance 的必须出现对仗）；
 * - 轮询读取（无 ADC 中断——模块 API 忙等单点实现）；
 * - 5 次快速平均（页面 3 次 × 100ms 间隔，us016 快平均先例改 5 次、去延时）；
 * - DO 数字量未声明（页面 get_raindrop_do_value（PA6，IPU）main 未用且 .h
 *   未声明——mspm0 先例「未用不声明」，不落 pins/不落码）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--rain-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、**百分比公式方向修正为正向映射（正文取证）并注释说明**、页面
 * ADC 序列收敛 ml_adc、3 次 × 100ms 间隔改 5 次快平均、get_adc_value 内
 * delay_ms(20) 去除、delay_1ms 换算并省略（快平均语义）、C99 循环声明改
 * uint8_t；页面 L97/102「GPIOC/GPIOE」串台——notes 记录不落码）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值
 * （正向映射：雨越大百分比越高——页面正文取证修正，页面原式反向矛盾） */
#define RAIN_ADC_MAX 4095u

/* 快速平均采样次数（页面 3 次 × 100ms 间隔，us016 快平均先例改 5 次） */
#define RAIN_ADC_SAMPLES 5u

/* rain_init：初始化 ADC1 对应通道（AO 模拟输入——页面 raindrop_gpio_config
 * 的 AIN 配置 + 6 分频 12MHz + 校准流程由 ml_adc 内部完成）。 */
void rain_init(void);

/* rain_read_percent：读 AO 分压对应的雨量百分比（0-100% 相对值——**正向
 * 映射**：雨越大百分比越高（页面正文「雨水越大→ADC 值越大」）；相对值非
 * 绝对值——雨滴板脏污/氧化/放置方式改变基线电阻，「值对应降雨量多少毫米需
 * 实体测量」（页面原话）；若实物分压方向相反改公式一处即可）。 */
float rain_read_percent(void);

#endif /* RAIN_STM32_H */
