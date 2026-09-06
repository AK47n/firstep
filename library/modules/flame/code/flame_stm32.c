/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《火焰传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/flame-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "flame_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 红外火焰传感器（stm32 纯驱动切片）：
 * - 通道 = 母版 pin_config.h 单源 FLAME_AO_CH（默认 ADC_Channel_5 = PA5——
 *   页面原脚：用户照页面接线即插即用）；**独立通道**——与 adc 模块 ADC_CH0/1
 *   不共读（与 mspm0 版独立 MEM6 语义同构：ml_adc 的 adc_get 每次先写 SQR3
 *   选通道再触发转换，顺序调用互不干扰；薄封装共读是 MEM 满后的回退，
 *   本件有通道可取——notes 记录）；
 * - 换算 percent = (1 - value/4095)×100（页面 Get_FLAME_Percentage_value
 *   原式——**反向映射**：红外光越强 ADC 值越小、百分比越高；相对强度非
 *   绝对值，受环境红外/器件差异影响）；
 * - 5 次快速平均（页面 SAMPLES 30 次 ×(20+5)ms 太慢——改 5 次快平均，
 *   mq2/us016/mspm0 版先例；真机行为差异 notes）；无采样延时（页面
 *   `delay_1ms(20)`——ml_delay 无 delay_1ms，换算 delay_ms(20) 也一并
 *   省略：快平均语义，页面缺陷记录）；
 * - DO 数字量未声明：页面 Get_FLAME_Do_value 走 LM393 阈值比较、阈值由
 *   模块可调电阻控制（mspm0 先例「未用不声明」= 同策略——不落 pins、
 *   不落码），需要时骨架经 gpio 直读。 */

void flame_init(void)
{
    /* 通道 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 复位校准（ml_adc 内部完成，
     * 等效页面 ADC_FLAME_Init 流程——采样时间 239.5cyc vs 页面 55.5cyc，
     * 功能等价差异 notes 记录） */
    adc_init(ADC_1, FLAME_AO_CH);
}

float flame_read_percent(void)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < FLAME_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, FLAME_AO_CH);
    }
    return (1.0f - (float)(sum / FLAME_ADC_SAMPLES) / (float)FLAME_ADC_MAX) * 100.0f;
}
