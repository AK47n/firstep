/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《MS1100气体传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ms1100-gas-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef MS1100_STM32_H
#define MS1100_STM32_H

#include <stdint.h>

/* MS1100 VOC 气体检测传感器（甲醛/苯系）驱动（stm32 纯驱动薄封装，ADR 0009）：
 * - **ADC 共享组共读**：经母版 ml_adc API 读 ADC1 通道（ms1100_init =
 *   adc_init(ADC_1, MS1100_AO_CH)；ADC 通道宏 MS1100_AO_CH 单源在
 *   pin_config.h，默认 ADC_Channel_5 = PA5——**页面原脚**（用户照页面接线
 *   即插即用）；本批与 batch5 八件 + flame 共读 PA5（ml_adc 顺序调用无扰）；
 *   同一物理脚只能接一件器件——多件同测需外部分路器/分时切换（mspm0 MEM0
 *   共读同口径）；
 * - 输出电压 → 浓度百分比：percent = value/4095×100（**页面无百分比函数**，
 *   由页面 demo 电压式 value/4095×3.3 推导——Vref 3.3V 满量程归一；
 *   **正向映射**：浓度越高 AOUT 电压越高、百分比越高；**相对值**，非 ppm
 *   精标；模块上电必须预热 3-5 分钟、真实浓度需标定；清洁空气电压 < 1V）；
 * - 轮询读取（无 ADC 中断——模块 API 忙等单点实现）；
 * - 5 次快速平均（页面 SAMPLES 30 次 × 3ms，us016 快平均先例改 5 次）；
 * - DOUT 数字量未声明（页面 Get_DO_Num/MS1100_DO——AOUT 与 4K 可调电阻
 *   比较，未用于演示——mspm0 先例「未用不声明」，不落 pins/不落码）；
 * - 与库内 sgp30/ags10（数字量 ppb/ppm VOC）分工：本件廉价模拟相对值。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--ms1100-gas-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、页面 ADC 序列收敛 ml_adc、SAMPLES 30→5 快平均、页面 demo 电压式
 * 推导归一 read_percent、DOUT 未用不声明）。多路气体同选共读 PA5 现实约束：
 * 同一引脚只能接一个器件；多路同时测需外部分路或换独立通道（stm32 通道
 * 10/10 全被既有角色占用）。 */

/* 百分比换算：12bit 满量程 4095（页面 demo 分母），输出 0-100% 相对值
 * （页面无百分比函数——由 demo 电压式 value/4095×3.3 推导归一） */
#define MS1100_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，us016 快平均先例改 5 次） */
#define MS1100_ADC_SAMPLES 5u

/* ms1100_init：初始化 ADC1 对应通道（AOUT 模拟输入——页面 MS1100_Init 的
 * AIN 配置 + 6 分频 12MHz + 校准流程由 ml_adc 内部完成）。 */
void ms1100_init(void);

/* ms1100_read_percent：读 AOUT 电压对应浓度百分比（0-100% 相对值——非 ppm
 * 精标；模块预热 3-5 分钟后读数才稳定；对甲醛/甲苯/苯等 VOC 灵敏）。 */
float ms1100_read_percent(void);

#endif /* MS1100_STM32_H */
