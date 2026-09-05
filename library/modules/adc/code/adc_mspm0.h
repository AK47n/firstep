#ifndef ADC_MSPM0_H
#define ADC_MSPM0_H

#include <stdint.h>

/* 模拟采样（双平台对偶 API，b1-adc-servo/01）：
 * - stm32 侧 = 母版 ml_adc 同名 API（ADCx_enum / ADCINx_enum 定义在 ml_adc.h，
 *   通道枚举 = 硬件通道 PA0-PC5）；
 * - mspm0 侧 = 本头（枚举兼容形态：通道枚举值 = ADC12 MEM 索引，
 *   v1 支持 0-7 八路——0 = 本模块默认脚（us016/mq2 共读）、1/2 = joystick 摇杆
 *   共享通道、3 = ir_distance 通道、4 = mq135、5 = mq5（wiki-modules-batch7：
 *   多路气体同选时各器件物理通道独立、无共读冲突）、6 = flame、7 = soil
 *   （wiki-modules-batch8：MEM 槽位 8/8 用满——后续 ADC 类件一律薄封装
 *   共读 MEM0，mq2/us016 先例））。
 * 引脚由生成器绑定（stm32 pin_config.h 宏 / mspm0 syscfg $assign），
 * 模块代码不吃引脚字面量。 */

typedef enum
{
    ADC_1, /* mspm0 单 ADC12，兼容 stm32 枚举形态 */
} ADCx_enum;

typedef enum
{
    ADC_Channel_0, /* MEM0（默认 PA24 / A0_3；adc 模块 + us016/mq2 薄封装共读） */
    ADC_Channel_1, /* MEM1（PA26 / A0_1——与 joystick 摇杆 X 共享同读一通道） */
    ADC_Channel_2, /* MEM2（PA25 / A0_2——归 joystick 摇杆 Y，adc_get 不开放） */
    ADC_Channel_3, /* MEM3（PA27 / A0_0——归 ir_distance 红外测距，adc_get 不开放） */
    ADC_Channel_4, /* MEM4（PB20 / A0_6——归 mq135，独立通道页内注释按共享约
                    * 定开放；多路气体同选时各器件物理通道独立、无共读冲突） */
    ADC_Channel_5, /* MEM5（PB24 / A0_5——归 mq5，同上） */
    ADC_Channel_6, /* MEM6（PA22 / A0_7——归 flame 火焰传感，独立通道；
                    * wiki-modules-batch8/01；MEM 槽位 8/8 用满后仅至 MEM7） */
    ADC_Channel_7,
    ADC_Channel_8,
    ADC_Channel_9,
    ADC_Channel_10,
    ADC_Channel_11,
    ADC_Channel_12,
    ADC_Channel_13,
    ADC_Channel_14,
    ADC_Channel_15,
} ADCINx_enum;

void adc_init(ADCx_enum adc, ADCINx_enum adc_channel);
uint16_t adc_get(ADCx_enum adc, ADCINx_enum adc_channel);

#endif
