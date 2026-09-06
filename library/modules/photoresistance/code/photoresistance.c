/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《光敏电阻光照传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/photoresistance-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "photoresistance.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM0（薄封装） */

/* 光敏电阻光照传感器（mspm0 纯驱动薄封装）：
 * - 依赖 adc 模块读 ADC12_0 MEM0 槽位（默认 PA24/A0_3）——不新开 ADC 通道；
 * - 换算 percent = (1 − value/4095)×100（页面 Get_illume_Percentage_value
 *   原式——**反向映射**：页面备注「最亮 100 最暗 0」自洽——光越强光敏电阻
 *   阻值越小（5516：光暗 ~1MΩ、光亮 8-20KΩ）、R2/R3 分压 ADC 值越小、
 *   百分比越高；相对强度非绝对值，非线性需标定）；
 * - 轮询读取，无 ADC 中断（共享 ADC12_0 实例：多模块同选时 IRQHandler 强
 *   符号须唯一，joystick/adc 先例）；
 * - 5 次快速平均（立创原版 10 次累加，us016 快平均先例）。 */

float photoresistance_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < PHOTORESISTANCE_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_0);
    }
    return (1.0f - (float)(sum / PHOTORESISTANCE_ADC_SAMPLES)
            / (float)PHOTORESISTANCE_ADC_MAX) * 100.0f;
}

void photoresistance_init(void)
{
    adc_init(ADC_1, ADC_Channel_0); /* 外设配置由 SYSCFG_DL_init() 完成 */
}
