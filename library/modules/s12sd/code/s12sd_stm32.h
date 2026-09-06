/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《S12SD紫外线传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/s12sd-uv-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef S12SD_STM32_H
#define S12SD_STM32_H

#include <stdint.h>

/* S12SD 紫外线传感器驱动（stm32 纯驱动薄封装，ADR 0009）：
 * - **ADC 共享组共读**：经母版 ml_adc API 读 ADC1 通道（s12sd_init =
 *   adc_init(ADC_1, S12SD_AO_CH)；ADC 通道宏 S12SD_AO_CH 单源在
 *   pin_config.h，默认 ADC_Channel_5 = PA5——**页面原脚**（用户照页面
 *   接线即插即用）；本批 8 件与 flame 共读 PA5（ml_adc 顺序调用无扰）；
 *   同一物理脚只能接一件器件——多件同测需外部分路器/分时切换（mspm0
 *   MEM0 共读同口径）；
 * - SIG 放大电压 → UV 指数：按页面 Get_Ultraviolet_Intensity 阈值表分档
 *   0-11 级（0 低 11 高——页面原式，阈值为 12bit ADC 值；检测波长
 *   240-370nm 即 UV-A 波段，UV-B/UV-C 不响应）；
 * - 轮询读取（无 ADC 中断——模块 API 忙等单点实现）；
 * - 5 次快速平均（页面 SAMPLES 30 次 × delay_ms(5)，us016 快平均先例改 5 次）；
 * - 无 DO（3 Pin：VCC/GND/SIG——页面无 DO 宏/函数）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--s12sd-uv-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、页面 ADC 序列收敛 ml_adc、SAMPLES 30→5 快平均、C99 循环声明改
 * uint8_t；页面 L289「IRtracking demo start」串台（IR 巡线模板残留）——
 * notes 记录不落码）。 */

/* 快速平均采样次数（页面 SAMPLES 30 次 × 5ms，us016 快平均先例改 5 次） */
#define S12SD_ADC_SAMPLES 5u

/* s12sd_init：初始化 ADC1 对应通道（SIG 模拟输入——页面 ULTRAVIOLET_GPIO_Init
 * 的 AIN 配置 + 6 分频 12MHz + 校准流程由 ml_adc 内部完成）。 */
void s12sd_init(void);

/* s12sd_read_uv_index：读 SIG 电压对应紫外线强度指数（0-11 级，0 低 11 高——
 * 页面阈值表原式；档位为页面标定值（页面实测室内 0 级）——户外强日光/遮挡/
 * 器件个体差异会偏移，按相对档位使用；检测波长 240-370nm（UV-A 波段））。 */
uint8_t s12sd_read_uv_index(void);

#endif /* S12SD_STM32_H */
