#ifndef ADC_MSPM0_H
#define ADC_MSPM0_H

#include <stdint.h>

/* 模拟采样（双平台对偶 API，b1-adc-servo/01）：
 * - stm32 侧 = 母版 ml_adc 同名 API（ADCx_enum / ADCINx_enum 定义在 ml_adc.h，
 *   通道枚举 = 硬件通道 PA0-PC5）；
 * - mspm0 侧 = 本头（枚举兼容形态：通道枚举值 = ADC12 MEM 索引，
 *   v1 支持 0/1 两路）。
 * 引脚由生成器绑定（stm32 pin_config.h 宏 / mspm0 syscfg $assign），
 * 模块代码不吃引脚字面量。 */

typedef enum
{
    ADC_1, /* mspm0 单 ADC12，兼容 stm32 枚举形态 */
} ADCx_enum;

typedef enum
{
    ADC_Channel_0, /* MEM0（默认 PA24 / A0_3；v1 只绑此通道） */
    ADC_Channel_1, /* MEM1（未绑引脚，v1 不可用——LQFP-64(PM) 无 adcPinN 槽位） */
    ADC_Channel_2,
    ADC_Channel_3,
    ADC_Channel_4,
    ADC_Channel_5,
    ADC_Channel_6,
    ADC_Channel_7,
    ADC_Channel_8,
    ADC_Channel_9,
    ADC_Channel_10,
    ADC_Channel_11,
    ADC_Channel_12,
    ADC_Channel_13,
    ADC_Channel_14,
    ADC_Channel_15,
} ADCINx_enum;

void adc_init(ADCx_enum adc, ADCINx_enum adc_channel);
uint16_t adc_get(ADCx_enum adc, ADCINx_enum adc_channel);

#endif
