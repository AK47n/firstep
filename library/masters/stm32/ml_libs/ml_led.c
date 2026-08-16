#include "ml_led.h"

/* 板载三色 LED 驱动（内嵌母版，led 模块 stm32 侧空条目 = 本实现）。
 * 灌电流接法：低电平点亮、高电平熄灭——极性封装在 led_on/off 内部。 */

typedef struct {
    GPIOn_enum port;
    Pinx_enum pin;
} ml_led_pin_t;

static const ml_led_pin_t LED_PINS[3] = {
    {LED_GPIO, LED_RED_Pin},    // LED_RED
    {LED_GPIO, LED_YELLOW_Pin}, // LED_YELLOW
    {LED_GPIO, LED_GREEN_Pin},  // LED_GREEN
};

static ml_led_pin_t led_pin(uint8_t channel)
{
    if (channel >= 3) {
        channel = LED_RED;
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
    gpio_set(led.port, led.pin, 0); // 灌电流：低电平点亮
}

void led_off(uint8_t channel)
{
    ml_led_pin_t led = led_pin(channel);
    gpio_set(led.port, led.pin, 1); // 高电平熄灭
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
