/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《MS1100气体传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ms1100-gas-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ms1100_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* MS1100 VOC 气体检测（stm32 纯驱动薄封装）：
 * - 通道 = 母版 pin_config.h 单源 MS1100_AO_CH（默认 ADC_Channel_5 = PA5——
 *   页面原脚：用户照页面接线即插即用）；**ADC 共享组**：本批 7 件与 batch5
 *   八件 + flame 共读 PA5（ml_adc 的 adc_get 每次先写 SQR3 选通道再触发
 *   转换，顺序调用互不干扰——flame 先例注释确认）；同一物理脚只能接一件
 *   器件，多件同测需外部分路器/分时切换（mspm0 MEM0 共读同口径——notes）；
 * - 换算 percent = value/4095×100（**页面无百分比函数**，由页面 demo 电压
 *   式 `voltage = (value/4095.0)×3.3`（Vref 3.3V）推导归一 → percent =
 *   voltage/3.3×100 = value/4095×100；**正向映射**：VOC 浓度越高 AOUT 电压
 *   越高、百分比越高；相对值非 ppm 精标：模块上电必须预热 3-5 分钟否则
 *   输出不准，真实浓度需标定）；
 * - 5 次快速平均（页面 SAMPLES 30 次 ×3ms 太慢——改 5 次快平均，
 *   us016/mspm0 版先例；无采样延时）；
 * - DOUT 数字量未声明：页面 Get_DO_Num/MS1100_DO（AOUT 与 4K 可调电阻
 *   比较）未用于演示（mspm0 先例「未用不声明」= 同策略，不落 pins、不落
 *   码），需要时骨架经 gpio 直读；
 * - 与库内 sgp30/ags10（数字量 ppb/ppm VOC）分工：本件廉价模拟相对值、
 *   两者数字绝对量。 */

void ms1100_init(void)
{
    /* 通道 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 复位校准（ml_adc 内部完成，
     * 等效页面 MS1100_Init 流程——采样时间 239.5cyc vs 页面 55.5cyc，
     * 功能等价差异 notes 记录） */
    adc_init(ADC_1, MS1100_AO_CH);
}

float ms1100_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < MS1100_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, MS1100_AO_CH);
    }
    return (float)(sum / MS1100_ADC_SAMPLES) / (float)MS1100_ADC_MAX * 100.0f;
}
