#include "ms1100.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM0（薄封装） */

/* MS1100 VOC 气体检测（mspm0 纯驱动薄封装）：
 * - 依赖 adc 模块读 ADC12_0 MEM0 槽位（默认 PA24/A0_3）——不新开 ADC 通道；
 * - 换算 percent = value/4095×100（页面 demo 电压式 value/4095×3.3 推导——
 *   页面无百分比函数；Vref 3.3V 满量程归一 → percent = voltage/3.3×100；
 *   **正向映射**：VOC 浓度越高 AOUT 电压越高、百分比越高；相对值非 ppm
 *   精标；模块上电必须预热 3-5 分钟否则输出不准）；
 * - 轮询读取，无 ADC 中断（共享 ADC12_0 实例：多模块同选时 IRQHandler 强
 *   符号须唯一，joystick/adc 先例）；
 * - 5 次快速平均（立创原版 30 次 ×3ms 太慢，us016 快平均先例）。 */

float ms1100_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < MS1100_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_0);
    }
    return (float)(sum / MS1100_ADC_SAMPLES) / (float)MS1100_ADC_MAX * 100.0f;
}

void ms1100_init(void)
{
    adc_init(ADC_1, ADC_Channel_0); /* 外设配置由 SYSCFG_DL_init() 完成 */
}
