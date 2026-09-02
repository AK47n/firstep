#include "led.h"
#include "ti_msp_dl_config.h"

/* 地猛星用户 LED 驱动（通道表见 led_instances.h：LED_CHANNEL_COUNT +
 * LED_PIN_TABLE——生成器多实例渲染产物；单实例默认 1 通道 PA15，LED_BEEP 组）。
 * 一脚接地、另一脚接引脚（拉电流）：高电平点亮、低电平熄灭。
 * 板载 PA0/PA1 被 I2C0（MPU6050）占用。 */

typedef struct {
    GPIO_Regs *port;
    uint32_t pin_mask;
} led_pin_t;

static const led_pin_t LED_PINS[LED_CHANNEL_COUNT] = LED_PIN_TABLE;

static led_pin_t led_pin(uint8_t channel)
{
    if (channel >= LED_CHANNEL_COUNT) {
        channel = 0; // 越界钳回首通道（led_instances.h 契约）
    }
    return LED_PINS[channel];
}

void led_init(uint8_t channel)
{
    led_off(channel); // SysConfig 已把各通道配置为输出（多实例 = 各自 GPIO 实例）
}

void led_on(uint8_t channel)
{
    led_pin_t led = led_pin(channel);
    DL_GPIO_setPins(led.port, led.pin_mask); // 高电平点亮
}

void led_off(uint8_t channel)
{
    led_pin_t led = led_pin(channel);
    DL_GPIO_clearPins(led.port, led.pin_mask); // 低电平熄灭
}

void led_toggle(uint8_t channel)
{
    led_pin_t led = led_pin(channel);
    DL_GPIO_togglePins(led.port, led.pin_mask);
}
