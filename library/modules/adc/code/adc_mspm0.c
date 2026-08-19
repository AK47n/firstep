#include "adc_mspm0.h"
#include "ti_msp_dl_config.h"

/* 模拟采样（mspm0，轮询单次转换）：ADC12_0 实例由母版 syscfg 提供
 * （v1 单通道 MEM0=PA24/A0_3；绑定换引脚时生成器改写 adcPin3.$assign +
 * adcMem0chansel，模块代码零改动；MEM1 未绑引脚，adc_channel=1 返回 0）。 */

void adc_init(ADCx_enum adc, ADCINx_enum adc_channel)
{
    (void)adc;
    (void)adc_channel; /* 外设配置由 SYSCFG_DL_init() 完成（模板 main.c 已调） */
    DL_ADC12_enableConversions(ADC12_0_INST);
}

uint16_t adc_get(ADCx_enum adc, ADCINx_enum adc_channel)
{
    (void)adc;
    if (adc_channel > ADC_Channel_1) {
        return 0; /* v1 只支持 MEM0/MEM1 两路 */
    }
    DL_ADC12_startConversion(ADC12_0_INST);
    /* SDK 2_10 的 getStatus 单参返回 STATUS 寄存器，busy 位 = ADC12_STATUS_BUSY_ACTIVE */
    while (DL_ADC12_getStatus(ADC12_0_INST) & ADC12_STATUS_BUSY_ACTIVE) {
    }
    uint16_t result =
        DL_ADC12_getMemResult(ADC12_0_INST, (DL_ADC12_MEM_IDX)adc_channel);
    DL_ADC12_enableConversions(ADC12_0_INST);
    return result;
}
