/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《MQ-5液化气检测传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/mq-5-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "mq5_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* MQ-5 液化气/天然气检测（stm32 纯驱动薄封装）：
 * - 通道 = 母版 pin_config.h 单源 MQ5_AO_CH（默认 ADC_Channel_5 = PA5——
 *   页面原脚：用户照页面接线即插即用）；**ADC 共享组**：本批 8 件与 flame
 *   共读 PA5（ml_adc 的 adc_get 每次先写 SQR3 选通道再触发转换，顺序调用
 *   互不干扰——flame 先例注释确认）；同一物理脚只能接一件器件，多件同测
 *   需外部分路器/分时切换（mspm0 MEM0 共读同口径——notes 记录）；
 * - 换算 percent = value/4095×100（页面 Get_MQ5_Percentage_value 原式——
 *   相对值非 ppm 精标：模块上电后 AO 电压随加热/环境/老化漂移，需预热
 *   几分钟、真实 ppm 需标准气体标定）；
 * - 5 次快速平均（页面 SAMPLES 30 次 × delay_ms(5) 太慢——改 5 次快平均，
 *   mq2/us016/mspm0 版先例；无采样延时）；C99 循环声明改 uint8_t i（库内
 *   模式，页面 for(int i...)）；
 * - DO 数字量未声明：页面 Get_MQ5_DO_value（PA1，IPU）演示未用
 *   （LM393 阈值由模块可调电阻控制——mspm0 先例「未用不声明」= 同策略，
 *   不落 pins、不落码），需要时骨架经 gpio 直读。 */

void mq5_init(void)
{
    /* 通道 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 复位校准（ml_adc 内部完成，
     * 等效页面 ADC_MQ5_Init 流程——采样时间 239.5cyc vs 页面 55.5cyc，
     * 功能等价差异 notes 记录） */
    adc_init(ADC_1, MQ5_AO_CH);
}

float mq5_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < MQ5_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, MQ5_AO_CH);
    }
    return (float)(sum / MQ5_ADC_SAMPLES) / (float)MQ5_ADC_MAX * 100.0f;
}
