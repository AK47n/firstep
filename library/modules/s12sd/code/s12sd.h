#ifndef S12SD_H
#define S12SD_H

#include <stdint.h>

/* S12SD 紫外线传感器驱动（mspm0 纯驱动薄封装，ADR 0009）：
 * - 薄封装：依赖库内 adc 模块读 ADC12_0 MEM0（adc_get(ADC_1, ADC_Channel_0)），
 *   不新开 ADC 通道——与 adc/us016/mq2 共享 MEM0 槽位（默认 PA24/A0_3）；
 * - SIG 放大电压 → UV 指数：按页面 Get_Ultraviolet_Intensity 阈值表分档
 *   0-11 级（0 低 11 高——页面原式，阈值为 12bit ADC 值；检测波长
 *   240-370nm 即 UV-A 波段，UV-B/UV-C 不响应）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 SAMPLES 30 次 × delay_ms(5)，us016 快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--s12sd-uv-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、30 次采样改 5 次快平均）。 */

/* 快速平均采样次数（页面 SAMPLES 30 次 × 5ms，us016 快平均先例改 5 次） */
#define S12SD_ADC_SAMPLES 5u

/* s12sd_init：使能 ADC12_0 转换（薄封装——adc_init 即 MEM0 轮询初始化）。 */
void s12sd_init(void);

/* s12sd_read_uv_index：读 SIG 电压对应紫外线强度指数（0-11 级，0 低 11 高——
 * 页面阈值表原式；档位为页面标定值（页面实测室内 0 级）——户外强日光/遮挡/
 * 器件个体差异会偏移，按相对档位使用；检测波长 240-370nm（UV-A 波段））。 */
uint8_t s12sd_read_uv_index(void);

#endif /* S12SD_H */
