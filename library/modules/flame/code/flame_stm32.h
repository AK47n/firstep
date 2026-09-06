/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《火焰传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/flame-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef FLAME_STM32_H
#define FLAME_STM32_H

#include <stdint.h>

/* 红外火焰传感器驱动（stm32，纯驱动切片，ADR 0009）：
 * - **独立 ADC 通道**：经母版 ml_adc API 读 ADC1 通道（flame_init =
 *   adc_init(ADC_1, FLAME_AO_CH)；ADC 通道宏 FLAME_AO_CH 单源在
 *   pin_config.h，默认 ADC_Channel_5 = PA5——**页面原脚**（用户照页面
 *   接线即插即用））——与 adc 模块 ADC_CH0/1 不共读（与 mspm0 版独立 MEM6
 *   语义同构；薄封装共读是 MEM 满后的回退，本件有通道可取）；
 * - 探测范围 700-1000nm 红外（灵敏度峰值 880nm、探测角度 60°），`红外光
 *   越强 ADC 值越小`——输出电压 → 火焰强度百分比为**反向映射**：percent =
 *   (1 - value/4095)×100（页面 Get_FLAME_Percentage_value 原式——**相对
 *   强度非绝对值**，受环境红外干扰/器件差异影响）；
 * - 轮询读取（无 ADC 中断——模块 API 忙等单点实现）;
 * - 5 次快速平均（页面 SAMPLES 30 次累加，mq2/us016 快平均先例）；
 * - DO 数字量未声明（页面 Get_FLAME_Do_value 走 LM393 阈值比较、阈值由
 *   模块可调电阻控制——mspm0 先例「未用不声明」，不落 pins/不落码）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--flame-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、页面 ADC 中断改轮询（页面已软件触发轮询——等价）、
 * delay_1ms→delay_ms 换算并省略采样延时、SAMPLES 30→5 快平均）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值
 * （反向映射：红外光越强 ADC 值越小、百分比越高） */
#define FLAME_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加 + delay_1ms(20)/delay_ms(5)
 * 采样延时，mq2 快平均先例改 5 次、去延时） */
#define FLAME_ADC_SAMPLES 5u

/* flame_init：初始化 ADC1 对应通道（AO 模拟输入——页面 ADC_FLAME_Init
 * 的 AIN 配置 + 6 分频 12MHz + 校准流程由 ml_adc 内部完成）。 */
void flame_init(void);

/* flame_read_percent：读 AO 电压对应火焰强度百分比（0-100% 相对值——反向
 * 映射：百分比越高火焰/热源红外越强；页面说明适用于 700-1000nm 波段，
 * 对日光/非火源热源可能误判，探测角度 60°）。 */
float flame_read_percent(void);

#endif /* FLAME_STM32_H */
