#include "beep_stm32.h"
#include "headfile.h"
#include "pin_config.h"

/* 有源蜂鸣器驱动（纯驱动切片）：BUZZER_GPIO/BUZZER_PIN 单源在 pin_config.h。
 * 极性：pin_config.h 约定低电平触发（有源蜂鸣器，低电平响）。 */

void beep_init(void)
{
    gpio_init(BUZZER_GPIO, BUZZER_PIN, OUT_PP);
    beep_off();
}

void beep_on(void)
{
    gpio_set(BUZZER_GPIO, BUZZER_PIN, 0);
}

void beep_off(void)
{
    gpio_set(BUZZER_GPIO, BUZZER_PIN, 1);
}

void beep_toggle(void)
{
    if (gpio_get(BUZZER_GPIO, BUZZER_PIN)) {
        beep_off();
    } else {
        beep_on();
    }
}

void beep_beep(uint16_t times, uint16_t on_ms, uint16_t off_ms)
{
    for (uint16_t i = 0; i < times; i++) {
        beep_on();
        delay_ms(on_ms);
        beep_off();
        if (i + 1 < times) {
            delay_ms(off_ms);
        }
    }
}
