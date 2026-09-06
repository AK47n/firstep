/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《雨滴传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/rain-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "rain_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 雨滴传感器（stm32 纯驱动薄封装）：
 * - 通道 = 母版 pin_config.h 单源 RAIN_AO_CH（默认 ADC_Channel_5 = PA5——
 *   页面原脚：用户照页面接线即插即用）；**ADC 共享组**：本批 8 件与 flame
 *   共读 PA5（ml_adc 的 adc_get 每次先写 SQR3 选通道再触发转换，顺序调用
 *   互不干扰——flame 先例注释确认）；同一物理脚只能接一件器件，多件同测
 *   需外部分路器/分时切换（mspm0 MEM0 共读同口径——notes 记录）；
 * - 换算 percent = value/4095×100（**方向修正**：页面原式
 *   (1 − value/4095)×100 与正文「雨水越大，电阻值越小，模拟值转化为的数字
 *   值越大」矛盾——两电极间水滴把导电板短路、电阻下降、AO 分压升高、ADC
 *   值增大，按正文改正向映射——mspm0 批 9 同款修正；**反向式防回潮守卫**：
 *   percent 公式不得出现 `1.0f - `，与 photoresistance 的必须出现对仗）；
 * - 5 次快速平均（页面 3 次 × delay_1ms(100) + get_adc_value 内 delay_ms(20)
 *   ≈460ms/次太慢——改 5 次快平均，us016/mspm0 版先例；delay_1ms 母版无此
 *   原语（ml_delay 无 delay_1ms，换算 delay_ms 也一并省略——快平均语义）；
 *   C99 循环声明改 uint8_t i）；
 * - DO 数字量未声明：页面 get_raindrop_do_value（PA6，IPU）main 未用且 .h
 *   未声明（LM393 阈值由模块可调电阻控制——mspm0 先例「未用不声明」= 同
 *   策略，不落 pins、不落码），需要时骨架经 gpio 直读。 */

void rain_init(void)
{
    /* 通道 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 复位校准（ml_adc 内部完成，
     * 等效页面 raindrop_gpio_config 流程——采样时间 239.5cyc vs 页面 55.5cyc，
     * 功能等价差异 notes 记录） */
    adc_init(ADC_1, RAIN_AO_CH);
}

float rain_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < RAIN_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, RAIN_AO_CH);
    }
    return (float)(sum / RAIN_ADC_SAMPLES) / (float)RAIN_ADC_MAX * 100.0f;
}
