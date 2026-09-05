#include "adc_mspm0.h"
#include "ti_msp_dl_config.h"

/* 模拟采样（mspm0，轮询多通道）：ADC12_0 实例由母版 syscfg 提供
 * （sequence 七通道：MEM0=PA24/A0_3 归本模块（us016/mq2 薄封装共读同槽——
 * wiki-modules-batch2/02、batch6/03），MEM1=PA26/A0_1 与 MEM2=PA25/A0_2 与
 * joystick 摇杆共享（wiki-modules-batch1/01），MEM3=PA27/A0_0 归
 * ir_distance（wiki-modules-batch2/04），MEM4=PB20/A0_6 归 mq135、
 * MEM5=PB24/A0_5 归 mq5（wiki-modules-batch7/01/02——独立通道使多路气体
 * 同选时各器件物理通道独立、无共读冲突），MEM6=PA22/A0_7 归 flame
 * （wiki-modules-batch8/01——独立通道、火焰 AO 高阻源取唯一无负载脚）；
 * 绑定换引脚时生成器改写 adcPin*.$assign + adcMem*chansel，模块代码零改动；
 * adc_get 通道 0-6 = MEM0-6，MEM1 与 joystick_read_x 同读一通道）。 */

void adc_init(ADCx_enum adc, ADCINx_enum adc_channel)
{
    (void)adc;
    (void)adc_channel; /* 外设配置由 SYSCFG_DL_init() 完成（模板 main.c 已调） */
    DL_ADC12_enableConversions(ADC12_0_INST);
}

uint16_t adc_get(ADCx_enum adc, ADCINx_enum adc_channel)
{
    (void)adc;
    if (adc_channel > ADC_Channel_6) {
        return 0; /* 本模块开放 MEM0-6：MEM0=本模块/us016/mq2（薄封装共读），
                   * MEM1=摇杆 X、MEM2=摇杆 Y、MEM3=ir_distance、MEM4=mq135、
                   * MEM5=mq5、MEM6=flame（共享实例同读——独立通道件同选时
                   * 物理通道独立，无共读冲突） */
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
