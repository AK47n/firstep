/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《S12SD紫外线传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/s12sd-uv-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "s12sd_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* S12SD 紫外线传感器（stm32 纯驱动薄封装）：
 * - 通道 = 母版 pin_config.h 单源 S12SD_AO_CH（默认 ADC_Channel_5 = PA5——
 *   页面原脚：用户照页面接线即插即用）；**ADC 共享组**：本批 8 件与 flame
 *   共读 PA5（ml_adc 的 adc_get 每次先写 SQR3 选通道再触发转换，顺序调用
 *   互不干扰——flame 先例注释确认）；同一物理脚只能接一件器件，多件同测
 *   需外部分路器/分时切换（mspm0 MEM0 共读同口径——notes 记录）；
 * - 换算 = 页面 Get_Ultraviolet_Intensity 阈值表原式（12bit ADC 值分档
 *   0-11 级，0 低 11 高；页面标注「0~11 紫外线强度等级由低到高，11 最高」）
 *   ——**非百分比**（本件与本批其余 7 件换算形态不同）；
 * - 5 次快速平均（页面 SAMPLES 30 次 × delay_ms(5) 太慢——改 5 次快平均，
 *   us016/mspm0 版先例；无采样延时）；C99 循环声明改 uint8_t i；
 * - 无 DO（3 Pin：VCC/GND/SIG——页面无 DO 宏/函数）。 */

void s12sd_init(void)
{
    /* 通道 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 复位校准（ml_adc 内部完成，
     * 等效页面 ULTRAVIOLET_GPIO_Init 流程——采样时间 239.5cyc vs 页面
     * 55.5cyc，功能等价差异 notes 记录） */
    adc_init(ADC_1, S12SD_AO_CH);
}

uint8_t s12sd_read_uv_index(void)
{
    uint32_t sum = 0;
    uint8_t i;
    uint16_t value;

    for (i = 0; i < S12SD_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, S12SD_AO_CH);
    }
    value = (uint16_t)(sum / S12SD_ADC_SAMPLES);

    if (value < 227u) {
        return 0; /* 紫外线强度 0 级 */
    }
    if (value < 318u) {
        return 1; /* 紫外线强度 1 级 */
    }
    if (value < 408u) {
        return 2; /* 紫外线强度 2 级 */
    }
    if (value < 503u) {
        return 3; /* 紫外线强度 3 级 */
    }
    if (value < 606u) {
        return 4; /* 紫外线强度 4 级 */
    }
    if (value < 696u) {
        return 5; /* 紫外线强度 5 级 */
    }
    if (value < 795u) {
        return 6; /* 紫外线强度 6 级 */
    }
    if (value < 881u) {
        return 7; /* 紫外线强度 7 级 */
    }
    if (value < 976u) {
        return 8; /* 紫外线强度 8 级 */
    }
    if (value < 1079u) {
        return 9; /* 紫外线强度 9 级 */
    }
    if (value < 1170u) {
        return 10; /* 紫外线强度 10 级 */
    }
    return 11; /* 紫外线强度 11 级（最高档：value >= 1170） */
}
