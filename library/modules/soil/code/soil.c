#include "soil.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM7（独立通道，
                        * 数据所有权归 adc 模块——busy 忙等单点实现） */

/* 土壤湿度传感器（mspm0 纯驱动切片）：
 * - 通道 MEM7（默认 PA14/A0_12——地猛星板上 ADC0 剩余通道仅 PA14（A0_12）：
 *   板载 LED2+15k 为固定比率衰减（读数系统偏小、单调性保留，阈值/趋势判断
 *   可用；要求精度时真机标定或改绑（无剩余 ADC 脚））；与 DCC_100_PWM2（step_motor 脉冲）/
 *   WS2812 IN（灯带）/RC522 SCK（读卡）/AGS10 SDA（气体）重叠——浇花/智慧
 *   农业与运动/读卡/气体不同框、同选概率最低，同选时经引脚绑定消解）；
 * - 换算 percent = value/4095×100（页面 Get_SH_Percentage_value 原式——
 *   **正向映射**：水分越足 ADC 值越大、百分比越高；相对湿度非绝对值，
 *   与土壤类型/压实度/器件差异有关）；
 * - 轮询读取经 adc 模块 API（adc_get(ADC_1, ADC_Channel_7)——busy 忙等
 *   单点实现，无重复拷贝；无 ADC 中断：共享实例 IRQHandler 强符号唯一）；
 * - 5 次快速平均（立创原版 Get_Adc_Value 30 次累加太慢，us016 快平均先例）。 */

float soil_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < SOIL_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_7);
    }
    return (float)(sum / SOIL_ADC_SAMPLES) / (float)SOIL_ADC_MAX * 100.0f;
}

void soil_init(void)
{
    adc_init(ADC_1, ADC_Channel_7); /* 外设配置由 SYSCFG_DL_init() 完成 */
}
