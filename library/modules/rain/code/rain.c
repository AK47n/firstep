#include "rain.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM0（薄封装） */

/* 雨滴传感器（mspm0 纯驱动薄封装）：
 * - 依赖 adc 模块读 ADC12_0 MEM0 槽位（默认 PA24/A0_3）——不新开 ADC 通道；
 * - 换算 percent = value/4095×100（**正向映射**：雨越大百分比越高——页面
 *   正文「雨水越大，电阻值越小，模拟值转化为的数字值越大」；页面原式
 *   (1 − value/4095)×100 与正文矛盾（照原式雨越大百分比反而越低——两电极
 *   间水滴把导电板短路、电阻下降、AO 分压升高、ADC 值增大），按「强度=
 *   水分覆盖=ADC 值关系」取证修正为正向映射；
 * - 轮询读取，无 ADC 中断（共享 ADC12_0 实例：多模块同选时 IRQHandler 强
 *   符号须唯一，joystick/adc 先例）；
 * - 5 次快速平均（立创原版 3 次 × 100ms 间隔带 delay_1ms(100)，us016 快
 *   平均先例——页面 get_adc_value 内 delay_ms(20) 一并去除）。 */

float rain_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < RAIN_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_0);
    }
    return (float)(sum / RAIN_ADC_SAMPLES) / (float)RAIN_ADC_MAX * 100.0f;
}

void rain_init(void)
{
    adc_init(ADC_1, ADC_Channel_0); /* 外设配置由 SYSCFG_DL_init() 完成 */
}
