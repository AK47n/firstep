/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《US-016超声波测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/us-016-ultrasonic-ranging-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "us016.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM0（薄封装） */

/* US-016 模拟量超声波（mspm0 纯驱动薄封装）：
 * - 依赖 adc 模块读 ADC12_0 MEM0 槽位（默认 PA24/A0_3）——不新开 ADC 通道；
 * - 换算 L = (A×3072/4096)×(Vref/Vcc) mm（Range 悬空/高 = 3m 量程，默认；
 *   手册正文「3096」与代码「3072」不一，按代码 0.75 系数）——Vref=Vcc=3.3V
 *   时 L = A×0.75mm；1m 量程（Range 接地）系数 0.25（US016_RANGE_1M=1）；
 * - 轮询读取，无 ADC 中断（共享 ADC12_0 实例：多模块同选时 IRQHandler 强
 *   符号须唯一，joystick/adc 先例）；
 * - 5 次快速平均（立创原版 50 次 × delay_ms(10) ≈ 500ms 太慢，摇杆先例）。 */

#define US016_ADC_SAMPLES 5 /* 快速平均采样次数（量程宏 US016_RANGE_1M 在头文件） */

void us016_init(void)
{
    adc_init(ADC_1, ADC_Channel_0); /* 外设配置由 SYSCFG_DL_init() 完成 */
}

float us016_read_distance_cm(void)
{
    uint32_t sum = 0;
    uint8_t i;
    float mm;

    for (i = 0; i < US016_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_0);
    }
#if US016_RANGE_1M
    mm = (float)(sum / US016_ADC_SAMPLES) * 0.25f; /* L = A×1024/4096 mm */
#else
    mm = (float)(sum / US016_ADC_SAMPLES) * 0.75f; /* L = A×3072/4096 mm */
#endif
    /* Vref/Vcc 修正（US016_VREF_V / US016_VCC_V，默认 3.3/3.3 = 1） */
    mm = mm * (US016_VREF_V / US016_VCC_V);
    return mm / 10.0f; /* mm → cm */
}
