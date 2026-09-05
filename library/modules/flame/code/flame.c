#include "flame.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM6（独立通道，
                        * 数据所有权归 adc 模块——busy 忙等单点实现） */

/* 红外火焰传感器（mspm0 纯驱动切片）：
 * - 通道 MEM6（默认 PA22/A0_7——地猛星板上 ADC0 剩余通道中 PA22 为唯一
 *   无负载脚：AO 直接取自光电二极管端子（高阻电流源），PA14 板载
 *   LED2+15k 会分流（mq5 选脚判据先例）；与 HUIDU L1（巡线）/DEBUG_UART
 *   RX/NRF24L01 IRQ/TTP224 OUT1 重叠——火警/灭火与巡线/无线/触摸不同框、
 *   同选概率最低，同选时经引脚绑定消解）；
 * - 换算 percent = (1 - value/4095)×100（页面
 *   Get_FLAME_Percentage_value 原式——**反向映射**：红外光越强 ADC 值
 *   越小、百分比越高；相对强度非绝对值，受环境红外/器件差异影响）；
 * - 轮询读取经 adc 模块 API（adc_get(ADC_1, ADC_Channel_6)——busy 忙等
 *   单点实现，无重复拷贝；无 ADC 中断：共享实例 IRQHandler 强符号唯一）；
 * - 5 次快速平均（立创原版 Get_Adc_FLAME_Value 30 次累加太慢，us016 快平均
 *   先例）。 */

float flame_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < FLAME_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_6);
    }
    return (1.0f - (float)(sum / FLAME_ADC_SAMPLES) / (float)FLAME_ADC_MAX) * 100.0f;
}

void flame_init(void)
{
    adc_init(ADC_1, ADC_Channel_6); /* 外设配置由 SYSCFG_DL_init() 完成 */
}
