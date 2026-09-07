/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《双轴按键摇杆模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/two-axis-keystroke-rocker-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "joystick_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 双轴摇杆按键（stm32 纯驱动）：
 * - 通道 = 母版 pin_config.h 单源 JOYSTICK_X_CH/JOYSTICK_Y_CH（默认
 *   ADC_Channel_1 = PA1 / ADC_Channel_0 = PA0——与 adc 模块 ADC_CH1/CH0
 *   **ADC 共享组**（mspm0 MEM1/2 与 adc 模块共享实例同构）；ml_adc 的
 *   adc_get 每次先写 SQR3 选通道再触发转换，顺序调用互不干扰）；同一物理
 *   脚只能接一件器件——多件同测需外部分路器/分时切换（mspm0 同口径）；
 * - SW 上拉输入低有效：JOYSTICK_SW_GPIO/PIN（默认 PA10——叠 DIGIT/COORD/
 *   UWB UART RX：摇杆与视觉/数传链路不同框、同选概率最低，同选经引脚绑定
 *   消解；mspm0 SW=PA9 同款推理）；
 * - 百分比 = (adc/4095)×100（页面原式归一整数——4 次快平均，
 *   mspm0 joystick.c 逐行口径）；
 * - 页面缺陷/修正（notes 记录）：页面每次读轴 30 × delay_ms(2) ≈ 60ms +
 *   2 次 ADC 校准无超时 → 4 次快平均；stm32 走 ml_adc 忙等（母版实现，
 *   无显式超时参数——与 mspm0 JOYSTICK_ADC_TIMEOUT 忙等超时口径差异
 *   记录）；L149 注释「Get_MQ2_Percentage_value」MQ2 串台不落码。 */

static uint16_t joystick_adc_read(ADCINx_enum channel)
{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < JOYSTICK_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, channel);
    }
    return (uint16_t)(sum / JOYSTICK_ADC_SAMPLES);
}

void joystick_init(void)
{
    /* 逐通道 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 复位校准（ml_adc 内部
     * 完成，等效页面 ADC_Joystick_Init 流程——每次调用含一次校准，启动时
     * 调用两次行为正确） */
    adc_init(ADC_1, JOYSTICK_X_CH);
    adc_init(ADC_1, JOYSTICK_Y_CH);
}

uint16_t joystick_read_x(void)
{
    return joystick_adc_read(JOYSTICK_X_CH);
}

uint16_t joystick_read_y(void)
{
    return joystick_adc_read(JOYSTICK_Y_CH);
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
    uint8_t level = gpio_get(JOYSTICK_SW_GPIO, JOYSTICK_SW_PIN) ? 1 : 0;
    return (level == JOYSTICK_SW_PRESSED_LEVEL) ? 1 : 0;
}
