/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《MQ-135空气质量传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-135-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "mq135.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM4（独立通道，
                        * 数据所有权归 adc 模块——busy 忙等单点实现） */

/* MQ-135 空气质量检测（mspm0 纯驱动切片）：
 * - 通道 MEM4（默认 PB20/A0_6——地猛星板上 ADC0 剩余通道中与既有默认
 *   同选概率最低者：与 DC_MOTOR BB（编码器）/SYN6288 TX（语音）重叠）；
 *   与 mq2 的 MEM0 薄封装（默认 PA24）不同——多路气体同选时物理通道独立、
 *   无共读冲突（绑定换引脚 = 改写 adcPin*.$assign + adcMem*chansel，模块零
 *   改动；页面原脚 PA27/A0_0 已归 ir_distance MEM3，复现手册接线需改绑）；
 * - 换算 percent = value/4095×100（页面 Get_MQ135_Percentage_value 原式——
 *   **相对值非 ppm 精标**：模块上电后 AO 电压随加热/环境/老化漂移，需预热
 *   几分钟、真实 ppm 需标准气体标定）；
 * - 轮询读取经 adc 模块 API（adc_get(ADC_1, ADC_Channel_4)——busy 忙等
 *   单点实现，无重复拷贝；无 ADC 中断：共享实例 IRQHandler 强符号唯一）；
 * - 5 次快速平均（立创原版 Get_Adc_MQ135_Value 30 次累加太慢，us016 快平均
 *   先例）。 */

float mq135_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < MQ135_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_4);
    }
    return (float)(sum / MQ135_ADC_SAMPLES) / (float)MQ135_ADC_MAX * 100.0f;
}

void mq135_init(void)
{
    adc_init(ADC_1, ADC_Channel_4); /* 外设配置由 SYSCFG_DL_init() 完成 */
}
