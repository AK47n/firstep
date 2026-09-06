/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《土壤湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/soil-moisture-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "soil_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 土壤湿度传感器（stm32 纯驱动薄封装）：
 * - 通道 = 母版 pin_config.h 单源 SOIL_AO_CH（默认 ADC_Channel_5 = PA5——
 *   页面原脚：用户照页面接线即插即用）；**ADC 共享组**：本批 8 件与 flame
 *   共读 PA5（ml_adc 的 adc_get 每次先写 SQR3 选通道再触发转换，顺序调用
 *   互不干扰——flame 先例注释确认）；同一物理脚只能接一件器件，多件同测
 *   需外部分路器/分时切换（mspm0 MEM0 共读同口径——notes 记录）；
 * - 换算 percent = value/4095×100（页面 Get_SH_Percentage_value 原式——
 *   正向映射：水分越足电导越高、AO 电压越大、百分比越高；相对湿度非绝对值，
 *   与土壤类型/压实度/器件差异有关）；**stm32 侧无 mspm0 板 PA14 板载
 *   LED2+15k 固定衰减问题**（mspm0 默认脚物理特性——stm32 默认 PA5 为排针
 *   ADC 脚无板载负载，notes 澄清）；
 * - 5 次快速平均（页面 SAMPLES 30 次 × delay_ms(5) 太慢——改 5 次快平均，
 *   us016/mspm0 版先例；无采样延时）；
 * - DO 数字量未声明：页面 Get_SH_DO_value（PA1，IPU）main 未用（LM393
 *   阈值由模块板载蓝色电位器控制——mspm0 先例「未用不声明」= 同策略，不落
 *   pins、不落码），需要时骨架经 gpio 直读。 */

void soil_init(void)
{
    /* 通道 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 复位校准（ml_adc 内部完成，
     * 等效页面 ADC_SOILHUMIDITY_Init 流程——采样时间 239.5cyc vs 页面
     * 55.5cyc，功能等价差异 notes 记录） */
    adc_init(ADC_1, SOIL_AO_CH);
}

float soil_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < SOIL_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, SOIL_AO_CH);
    }
    return (float)(sum / SOIL_ADC_SAMPLES) / (float)SOIL_ADC_MAX * 100.0f;
}
