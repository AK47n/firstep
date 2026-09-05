#include "ir_distance.h"
#include <math.h> /* pow：GP2Y0A02YK0F 电压→距离换算 */
#include "ti_msp_dl_config.h" /* ADC12_0_INST / ADC12_0_ADCMEM_3 */

/* GP2Y0A02YK0F 红外测距（mspm0 纯驱动）：
 * - 独立通道 MEM3（default PA27/A0_0——手册原脚；与 adc/us016/joystick 共享
 *   ADC12_0 实例，sequence 四通道模式——单发模式只启用 startAdd 槽位，
 *   2026-09-05 SysConfig CLI 实证）；
 * - 轮询读取（无 ADC 中断：共享实例的 IRQHandler 强符号须唯一，joystick 先例）；
 * - VREF 默认 3.3V（地猛星 3V3 供电；引用其他基准改 IR_DIST_VREF_V 一处）；
 * - <15cm 时电压急剧跌落（≈远距读数），安装位置须避开该区域（手册警告）。 */

#define IR_DIST_ADC_SAMPLES 10 /* 采样平均次数（手册 Get_Adc_Value(10.f) 原值） */
#define IR_DIST_ADC_MAX 4095   /* 12bit 满量程 */
#define IR_DIST_VREF_V 3.3f    /* ADC 参考电压（= 模块供电 Vcc 时换算最准） */
#define IR_DIST_ADC_TIMEOUT 200 /* 忙等超时圈数（防转换器卡死；超时返回 0） */

void ir_distance_init(void)
{
    /* SysConfig 已配 ADC12_0（sequence 四通道）+ 引脚；此处仅确保转换使能 */
    DL_ADC12_enableConversions(ADC12_0_INST);
}

float ir_distance_read_distance_cm(void)
{
    uint32_t sum = 0;
    uint8_t i;
    float volts;
    float distance;

    for (i = 0; i < IR_DIST_ADC_SAMPLES; i++) {
        DL_ADC12_startConversion(ADC12_0_INST);
        int32_t timeout = IR_DIST_ADC_TIMEOUT;
        while (DL_ADC12_getStatus(ADC12_0_INST) & ADC12_STATUS_BUSY_ACTIVE) {
            if (--timeout <= 0) {
                return 0.0f; /* 采样超时：转换器未就绪 */
            }
        }
        sum += DL_ADC12_getMemResult(ADC12_0_INST, ADC12_0_ADCMEM_3);
    }
    if (sum == 0) {
        return 0.0f; /* 全 0 = 未接传感器/引脚悬空，避免 pow(0, -1.16) 溢出 */
    }
    volts = ((float)(sum / IR_DIST_ADC_SAMPLES) / (float)IR_DIST_ADC_MAX)
            * IR_DIST_VREF_V;
    /* GP2Y0A02YK0F 官方公式（20-150cm 段）：Distance = 60.374 × V^(-1.16) */
    distance = 60.374f * (float)pow((double)volts, -1.16);
    return distance;
}
