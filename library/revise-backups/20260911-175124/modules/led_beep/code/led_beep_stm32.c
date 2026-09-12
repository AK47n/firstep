#include "led_beep_stm32.h"
#include "beep_stm32.h"
#include "headfile.h"  // ml_led.h（led_init/led_on/led_off）内嵌母版

/* 组合模块（stm32）：转发 led / beep，只做同时控制。 */

void led_beep_init(void)
{
    led_init(LED_RED);
    beep_init();
}

void led_beep_on(void)
{
    led_on(LED_RED);
    beep_on();
}

void led_beep_off(void)
{
    led_off(LED_RED);
    beep_off();
}

void led_beep_alarm(uint16_t times, uint16_t on_ms, uint16_t off_ms)
{
    for (uint16_t i = 0; i < times; i++) {
        led_beep_on();
        delay_ms(on_ms);
        led_beep_off();
        if (i + 1 < times) {
            delay_ms(off_ms);
        }
    }
}
