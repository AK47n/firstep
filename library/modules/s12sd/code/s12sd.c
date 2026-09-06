/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《S12SD紫外线传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/s12sd-uv-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "s12sd.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM0（薄封装） */

/* S12SD 紫外线传感器（mspm0 纯驱动薄封装）：
 * - 依赖 adc 模块读 ADC12_0 MEM0 槽位（默认 PA24/A0_3）——不新开 ADC 通道；
 * - 换算 = 页面 Get_Ultraviolet_Intensity 阈值表原式（12bit ADC 值分档
 *   0-11 级，0 低 11 高；页面标注「0~11 紫外线强度等级由低到高，11 最高」）；
 * - 轮询读取，无 ADC 中断（共享 ADC12_0 实例：多模块同选时 IRQHandler 强
 *   符号须唯一，joystick/adc 先例）；
 * - 5 次快速平均（立创原版 SAMPLES 30 次 × delay_ms(5)，us016 快平均先例）。 */

uint8_t s12sd_read_uv_index(void)
{
    uint32_t sum = 0;
    uint8_t i;
    uint16_t value;

    for (i = 0; i < S12SD_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_0);
    }
    value = (uint16_t)(sum / S12SD_ADC_SAMPLES);

    if (value < 227u) {
        return 0; /* 紫外线强度 0 级 */
    }
    if (value < 318u) {
        return 1; /* 紫外线强度 1 级 */
    }
    if (value < 408u) {
        return 2; /* 紫外线强度 2 级 */
    }
    if (value < 503u) {
        return 3; /* 紫外线强度 3 级 */
    }
    if (value < 606u) {
        return 4; /* 紫外线强度 4 级 */
    }
    if (value < 696u) {
        return 5; /* 紫外线强度 5 级 */
    }
    if (value < 795u) {
        return 6; /* 紫外线强度 6 级 */
    }
    if (value < 881u) {
        return 7; /* 紫外线强度 7 级 */
    }
    if (value < 976u) {
        return 8; /* 紫外线强度 8 级 */
    }
    if (value < 1079u) {
        return 9; /* 紫外线强度 9 级 */
    }
    if (value < 1170u) {
        return 10; /* 紫外线强度 10 级 */
    }
    return 11; /* 紫外线强度 11 级（最高档：value >= 1170） */
}

void s12sd_init(void)
{
    adc_init(ADC_1, ADC_Channel_0); /* 外设配置由 SYSCFG_DL_init() 完成 */
}
