/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《MQ-6丙烷检测传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-6-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef MQ6_H
#define MQ6_H

#include <stdint.h>

/* MQ-6 液化气/丙烷检测传感器驱动（mspm0 纯驱动薄封装，ADR 0009）：
 * - 薄封装：依赖库内 adc 模块读 ADC12_0 MEM0（adc_get(ADC_1, ADC_Channel_0)），
 *   不新开 ADC 通道——mq6 与 adc/us016/mq2/批次 9 四件共享 MEM0 槽位
 *   （默认 PA24/A0_3）；
 * - 输出电压 → 浓度百分比：percent = value/4095×100（页面原式——**正向映射**：
 *   浓度越高 ADC 值越高、百分比越高；**相对值**，非 ppm 精标；模块上电需预热
 *   3-5 分钟、湿度影响读数、真实 ppm 需标准气体标定）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 30 次×5ms，按 us016 快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--mq-6-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、DO 数字量阈值未声明——页面 Get_MQ6_DO_value
 * 仅定义未用于演示）。多路气体同选共读 MEM0 现实约束：同一引脚 PA24 只能接
 * 一个器件；多路同时测需外部分路或换独立通道（MEM 槽位已满 8/8）。
 * 取证：「传感器的电导率随空气中可燃气体浓度的增加而增大」 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值 */
#define MQ6_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，us016 快平均先例改 5 次） */
#define MQ6_ADC_SAMPLES 5u

/* mq6_init：使能 ADC12_0 转换（薄封装——adc_init 即 MEM0 轮询初始化）。 */
void mq6_init(void);

/* mq6_read_percent：读 AO 电压对应浓度百分比（0-100% 相对值——MQ 系读数
 * 随环境/老化漂移，非 ppm 精标；模块预热后读数才稳定）。 */
float mq6_read_percent(void);

#endif /* MQ6_H */
