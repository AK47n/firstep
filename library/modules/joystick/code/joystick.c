#include "joystick.h"
#include "ti_msp_dl_config.h"

/* 双轴摇杆按键（mspm0 纯驱动）：X/Y 走 ADC12_0 MEM1/MEM2（与 adc 模块共享
 * 实例，sequence 四通道——单发模式只启用 startAdd 槽位，SysConfig CLI
 * 实证；MEM3 归 ir_distance，wiki-modules-batch2/04），SW 上拉输入低有效。
 * 轮询读取（照 adc 模块先例）；4 次快速平均降噪
 * （立创原版 30 次 × delay_ms(5) 太慢，摇杆需实时，已按库规范改造）。 */

#define JOYSTICK_ADC_MAX 4095      /* 12bit 满量程 */
#define JOYSTICK_ADC_SAMPLES 4     /* 快速平均采样次数 */
#define JOYSTICK_ADC_TIMEOUT 50    /* 忙等超时圈数（防卡死，超时返回上次值） */

static uint16_t _joystick_adc_read(DL_ADC12_MEM_IDX mem)
{
    uint32_t sum = 0;
    for (uint32_t i = 0; i < JOYSTICK_ADC_SAMPLES; i++) {
        DL_ADC12_startConversion(ADC12_0_INST);
        int32_t timeout = JOYSTICK_ADC_TIMEOUT;
        while (DL_ADC12_getStatus(ADC12_0_INST) & ADC12_STATUS_BUSY_ACTIVE) {
            if (--timeout <= 0) {
                return (uint16_t)(sum / (i ? i : 1)); /* 超时：返回已采样均值 */
            }
        }
        sum += DL_ADC12_getMemResult(ADC12_0_INST, mem);
    }
    return (uint16_t)(sum / JOYSTICK_ADC_SAMPLES);
}

void joystick_init(void)
{
    /* SysConfig 已配 ADC12_0（四通道 sequence）+ JOYSTICK（上拉输入），
     * 由模板 SYSCFG_DL_init() 生效；此处仅确保转换使能。 */
    DL_ADC12_enableConversions(ADC12_0_INST);
}

uint16_t joystick_read_x(void)
{
    return _joystick_adc_read(ADC12_0_ADCMEM_1);
}

uint16_t joystick_read_y(void)
{
    return _joystick_adc_read(ADC12_0_ADCMEM_2);
}

uint16_t joystick_read_x_percent(void)
{
    return (uint16_t)(((uint32_t)joystick_read_x() * 100u) / JOYSTICK_ADC_MAX);
}

uint16_t joystick_read_y_percent(void)
{
    return (uint16_t)(((uint32_t)joystick_read_y() * 100u) / JOYSTICK_ADC_MAX);
}

uint8_t joystick_read_sw(void)
{
    uint32_t bits = DL_GPIO_readPins(JOYSTICK_PORT, JOYSTICK_SW_PIN);
    uint8_t level = (bits & JOYSTICK_SW_PIN) ? 1 : 0;
    return (level == JOYSTICK_SW_PRESSED_LEVEL) ? 1 : 0;
}
