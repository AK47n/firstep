/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《MQ-5液化气检测传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-5-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "mq5.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM5（独立通道，
                        * 数据所有权归 adc 模块——busy 忙等单点实现） */

/* MQ-5 液化气/天然气检测（mspm0 纯驱动切片）：
 * - 通道 MEM5（默认 PB24/A0_5——地猛星板上 ADC0 剩余通道中与既有默认
 *   同选概率最低者：候选 PA14 板载 LED2+15k 负载不适合作 ADC 模拟输入
 *   （模拟输入会被 15k 分流），PA22 的 DEBUG_UART RX/HUIDU L1/NRF IRQ/
 *   TTP224 OUT1 与气体检测的巡线巡检车/无线气体站/触摸面板环境站更常同框；
 *   与 STEP_MOTOR RST2/SR04 TRIG/HC05 KEY/AT24C02 SCL 重叠）；
 *   与 mq2 的 MEM0 薄封装（默认 PA24）不同——多路气体同选时物理通道独立、
 *   无共读冲突（绑定换引脚 = 改写 adcPin*.$assign + adcMem*chansel，模块零
 *   改动）；
 * - 换算 percent = value/4095×100（页面 Get_MQ5_Percentage_value 原式——
 *   **相对值非 ppm 精标**：模块上电后 AO 电压随加热/环境/老化漂移，需预热
 *   几分钟、真实 ppm 需标准气体标定）；
 * - 轮询读取经 adc 模块 API（adc_get(ADC_1, ADC_Channel_5)——busy 忙等
 *   单点实现，无重复拷贝；无 ADC 中断：共享实例 IRQHandler 强符号唯一）；
 * - 5 次快速平均（立创原版 Get_Adc_MQ5_Value 30 次累加太慢，us016 快平均
 *   先例）。 */

float mq5_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < MQ5_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_5);
    }
    return (float)(sum / MQ5_ADC_SAMPLES) / (float)MQ5_ADC_MAX * 100.0f;
}

void mq5_init(void)
{
    adc_init(ADC_1, ADC_Channel_5); /* 外设配置由 SYSCFG_DL_init() 完成 */
}
