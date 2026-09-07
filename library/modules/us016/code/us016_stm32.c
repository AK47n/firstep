/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《US-016超声波测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/us-016-ultrasonic-ranging-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "us016_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* US-016 模拟量超声波（stm32 纯驱动薄封装）：
 * - 通道 = 母版 pin_config.h 单源 US016_AO_CH（默认 ADC_Channel_5 = PA5——
 *   页面原脚即共读点）；**ADC 共享组**：与 flame/批 5/6 件 + ir_distance
 *   互替件同脚共读（ml_adc 的 adc_get 每次先写 SQR3 选通道再触发转换，
 *   顺序调用互不干扰）；同一物理脚只能接一件器件——多件同测需外部分路器/
 *   分时切换（mspm0 MEM0 共读同口径，notes 记录）；
 * - 换算 L = (A×3072/4096)×(Vref/Vcc) mm（Range 悬空/高 = 3m 量程，默认；
 *   手册正文「3096」与代码「3072」不一，按代码 0.75 系数）——Vref=Vcc=3.3V
 *   时 L = A×0.75mm；1m 量程（Range 接地）系数 0.25（US016_RANGE_1M=1）；
 * - 轮询读取（ml_adc 忙等单点实现，无 ADC 中断）；
 * - 5 次快速平均（页面 50 次 × delay_ms(10) ≈ 500ms 阻塞采样太慢，mspm0/
 *   us016 快平均先例）；出参 cm = mm/10（页面 main L254 换算归入 API）。 */

void us016_init(void)
{
    /* 通道 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 复位校准（ml_adc 内部完成，
     * 等效页面 US016_GPIO_Init 流程） */
    adc_init(ADC_1, US016_AO_CH);
}

float us016_read_distance_cm(void)
{
    uint32_t sum = 0;
    uint8_t i;
    float mm;

    for (i = 0; i < US016_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, US016_AO_CH);
    }
#if US016_RANGE_1M
    mm = (float)(sum / US016_ADC_SAMPLES) * 0.25f; /* L = A×1024/4096 mm */
#else
    mm = (float)(sum / US016_ADC_SAMPLES) * 0.75f; /* L = A×3072/4096 mm */
#endif
    /* Vref/Vcc 修正（US016_VREF_V / US016_VCC_V，默认 3.3/3.3 = 1） */
    mm = mm * (US016_VREF_V / US016_VCC_V);
    return mm / 10.0f; /* mm → cm（照 mspm0 us016_read_distance_cm 出参） */
}
