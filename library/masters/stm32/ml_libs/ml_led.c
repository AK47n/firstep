#include "ml_led.h"

/* 泛型 LED 驱动（内嵌母版，led 模块 stm32 侧空条目 = 本实现）。
 * 通道表来自 led_instances.h（LED_CHANNEL_COUNT + LED_PIN_TABLE——生成器
 * 多实例渲染产物；单实例默认三通道 PC13/14/15，引脚取 pin_config.h）。
 * LED 一脚接地、另一脚接 MCU 引脚（拉电流接法）：高电平点亮、低电平熄灭。
 * 极性封装在 led_on/off 内部，调用方只认 led_on = 亮。 */

typedef struct {
    GPIOn_enum port;
    Pinx_enum pin;
} ml_led_pin_t;

static const ml_led_pin_t LED_PINS[LED_CHANNEL_COUNT] = LED_PIN_TABLE;

static ml_led_pin_t led_pin(uint8_t channel)
{
    if (channel >= LED_CHANNEL_COUNT) {
        channel = 0; // 越界钳回首通道（led_instances.h 契约）
    }
    return LED_PINS[channel];
}

void led_init(uint8_t channel)
{
    ml_led_pin_t led = led_pin(channel);
    gpio_init(led.port, led.pin, OUT_PP);
    led_off(channel);
}

void led_on(uint8_t channel)
{
    ml_led_pin_t led = led_pin(channel);
    gpio_set(led.port, led.pin, 1); // 拉电流：高电平点亮
}

void led_off(uint8_t channel)
{
    ml_led_pin_t led = led_pin(channel);
    gpio_set(led.port, led.pin, 0); // 低电平熄灭
}

void led_toggle(uint8_t channel)
{
    ml_led_pin_t led = led_pin(channel);
    if (gpio_get(led.port, led.pin)) {
        led_on(channel);
    } else {
        led_off(channel);
    }
}
