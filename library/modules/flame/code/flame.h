#ifndef FLAME_H
#define FLAME_H

#include <stdint.h>

/* 红外火焰传感器驱动（mspm0 纯驱动切片，ADR 0009）：
 * - **独立 ADC 通道**：经库内 adc 模块 API 读 ADC12_0 MEM6（adc_get(ADC_1,
 *   ADC_Channel_6)，默认 PA22/A0_7，母版 sequence 七通道 endAdd=6）——
 *   与 mq2/us016 的 MEM0 薄封装不同：火焰与其它模拟量件同选时物理通道
 *   独立、无共读冲突（本件取剩余 MEM 槽位 MEM6）；
 * - 探测范围 700-1000nm 红外（灵敏度峰值 880nm、探测角度 60°），`红外光
 *   越强 ADC 值越小`——输出电压 → 火焰强度百分比为**反向映射**：percent =
 *   (1 - value/4095)×100（页面 Get_FLAME_Percentage_value 原式——**相对
 *   强度非绝对值**，受环境红外干扰/器件差异影响）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 SAMPLES 30 次累加，mq2/us016 快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--flame-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、DO 数字量阈值未声明——页面 Get_FLAME_Do_value
 * 走 LM393 阈值比较、阈值由模块可调电阻控制）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值
 * （反向映射：红外光越强 ADC 值越小、百分比越高） */
#define FLAME_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，mq2 快平均先例改 5 次） */
#define FLAME_ADC_SAMPLES 5u

/* flame_init：使能 ADC12_0 转换（独立 MEM6 通道轮询——adc_init 即初始化）。 */
void flame_init(void);

/* flame_read_percent：读 AO 电压对应火焰强度百分比（0-100% 相对值——反向
 * 映射：百分比越高火焰/热源红外越强；页面说明适用于 700-1000nm 波段，
 * 对日光/非火源热源可能误判，探测角度 60°）。 */
float flame_read_percent(void);

#endif /* FLAME_H */
