#include "ml_led.h"

void led_init(void)
{
    gpio_init(LED_GPIO, LED_RED_Pin, OUT_PP);
    gpio_init(LED_GPIO, LED_GREEN_Pin, OUT_PP);

    // 初始状态：两个LED都熄灭
    LED_RED_OFF();
    LED_GREEN_OFF();
}
