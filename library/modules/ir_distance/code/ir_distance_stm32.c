/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《红外测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/Infrared-distance-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ir_distance_stm32.h"
#include "pin_config.h"
#include "headfile.h"
#include <math.h> /* powf：GP2Y0A02YK0F 电压→距离换算（ARMCC 标准库自动含） */

/* GP2Y0A02YK0F 红外测距（stm32 纯驱动薄封装）：
 * - 通道 = 母版 pin_config.h 单源 IR_DISTANCE_AO_CH（默认 ADC_Channel_5 =
 *   PA5——页面原脚即共读点）；**ADC 共享组**：与 us016 互替件同脚（同一物理
 *   脚只能接一件——互替同脚先例；同选经绑定其一换 PA0/PA1）、与 flame/
 *   批次 5/6 件共读 PA5（ml_adc 的 adc_get 每次先写 SQR3 选通道再触发转换，
 *   顺序调用互不干扰）；多件同测需外部分路器/分时切换（mspm0 MEM 共读同
 *   口径，notes 记录）；
 * - 换算 V = raw/4095×3.3（页面硬编码 3.5V → 3.3V 宏化修正——3.3V 供电
 *   下页面换算系统偏低约 6%）、Distance = 60.374×V^(-1.16)（20-150cm 段；
 *   <15cm 电压跌落非线性区随注释）；
 * - 轮询读取（ml_adc 忙等单点实现，无 ADC 中断）；10 次快速平均（手册
 *   Get_Adc_Value(10) 原值——非 5 次快平均口径，mspm0 同）；
 * - 全 0 采样返回 0.0f（防 pow(0,-1.16) 溢出——原版输出 inf，mspm0 先例）。 */

void ir_distance_init(void)
{
    /* 通道 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 复位校准（ml_adc 内部完成，
     * 等效页面 IRdistance_GPIO_Init 流程） */
    adc_init(ADC_1, IR_DISTANCE_AO_CH);
}

float ir_distance_read_distance_cm(void)
{
    uint32_t sum = 0;
    uint8_t i;
    float volts;
    float distance;

    for (i = 0; i < IR_DIST_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, IR_DISTANCE_AO_CH);
    }
    if (sum == 0) {
        return 0.0f; /* 全 0 = 未接传感器/引脚悬空，避免 pow(0,-1.16) 溢出 */
    }
    volts = ((float)(sum / IR_DIST_ADC_SAMPLES) / (float)IR_DIST_ADC_MAX)
            * IR_DIST_VREF_V;
    /* GP2Y0A02YK0F 官方公式（20-150cm 段）：Distance = 60.374 × V^(-1.16)；
     * stm32 用 powf 单精度（C8T6 无硬件 FPU 软浮点省栈；与 mspm0 double pow
     * 同精度级——notes 记录） */
    distance = 60.374f * powf(volts, -1.16f);
    return distance;
}
