/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《MQ-9可燃气体检测传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-9-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "mq9.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM0（薄封装） */

/* MQ-9 一氧化碳/可燃气体检测传感器（mspm0 纯驱动薄封装）：
 * - 依赖 adc 模块读 ADC12_0 MEM0 槽位（默认 PA24/A0_3）——不新开 ADC 通道；
 * - 换算 percent = value/4095×100（页面 Get_MQ9_Percentage_value 原式——
 *   **正向映射**：气敏电导率随检测气体浓度增加而增大、AO 电压越高、百分比越高；相对值非
 *   ppm 精标；模块上电后 AO 电压随加热漂移，需预热/标定）；
 * - 轮询读取，无 ADC 中断（共享 ADC12_0 实例：多模块同选时 IRQHandler 强
 *   符号须唯一，joystick/adc 先例）；
 * - 5 次快速平均（立创原版 30 次 ×5ms 太慢，us016 快平均先例）。 */

float mq9_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < MQ9_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_0);
    }
    return (float)(sum / MQ9_ADC_SAMPLES) / (float)MQ9_ADC_MAX * 100.0f;
}

void mq9_init(void)
{
    adc_init(ADC_1, ADC_Channel_0); /* 外设配置由 SYSCFG_DL_init() 完成 */
}
