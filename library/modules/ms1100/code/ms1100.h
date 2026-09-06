#ifndef MS1100_H
#define MS1100_H

#include <stdint.h>

/* MS1100 VOC 气体检测传感器（甲醛/苯系）驱动（mspm0 纯驱动薄封装，ADR 0009）：
 * - 薄封装：依赖库内 adc 模块读 ADC12_0 MEM0（adc_get(ADC_1, ADC_Channel_0)），
 *   不新开 ADC 通道——ms1100 与 adc/us016/mq2/批次 9 四件共享 MEM0 槽位
 *   （默认 PA24/A0_3）；
 * - 输出电压 → 浓度百分比：percent = value/4095×100（**页面无百分比函数**，
 *   由页面 demo 电压式 value/4095×3.3 推导——Vref 3.3V 满量程归一；
 *   **正向映射**：浓度越高 AOUT 电压越高、百分比越高；**相对值**，非 ppm
 *   精标；模块上电必须预热 3-5 分钟、真实浓度需标定）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 30 次×3ms，按 us016 快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--ms1100-gas-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、DO 数字量阈值未声明——页面 Get_DO_Num/MS1100_DO
 * 仅定义未用于演示）。多路气体同选共读 MEM0 现实约束：同一引脚 PA24 只能接
 * 一个器件；多路同时测需外部分路或换独立通道（MEM 槽位已满 8/8）。
 * 取证：「AOUT 为芯片检测到的气体量对应的电压值变化」「清洁空气中电压 < 1V」 */

/* 百分比换算：12bit 满量程 4095（页面 demo 分母），输出 0-100% 相对值 */
#define MS1100_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，us016 快平均先例改 5 次） */
#define MS1100_ADC_SAMPLES 5u

/* ms1100_init：使能 ADC12_0 转换（薄封装——adc_init 即 MEM0 轮询初始化）。 */
void ms1100_init(void);

/* ms1100_read_percent：读 AOUT 电压对应浓度百分比（0-100% 相对值——非 ppm 精标；
 * 模块预热 3-5 分钟后读数才稳定）。 */
float ms1100_read_percent(void);

#endif /* MS1100_H */
