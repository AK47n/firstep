#include "adc_mspm0.h"
#include "ti_msp_dl_config.h"

/* 模拟采样（mspm0，轮询多通道）：ADC12_0 实例由母版 syscfg 提供
 * （sequence 三通道：MEM0=PA24/A0_3 归本模块，MEM1=PA26/A0_1 与
 * MEM2=PA25/A0_2 与 joystick 摇杆共享——wiki-modules-batch1/01；
 * 绑定换引脚时生成器改写 adcPin*.$assign + adcMem*chansel，模块代码零改动；
 * adc_get 通道 0/1 = MEM0/MEM1，MEM1 与 joystick_read_x 同读一通道）。 */

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
        return 0; /* 本模块开放 MEM0/MEM1 两路（MEM2 归摇杆 Y） */
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
