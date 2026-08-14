#include "led_beep.h"

void led_on()
{
    DL_GPIO_setPins(LED_BEEP_PORT, LED_BEEP_LED_PIN);
}
void led_off()
{
    DL_GPIO_clearPins(LED_BEEP_PORT, LED_BEEP_LED_PIN);
}

void beep_on()
{
    // 蜂鸣器暂不使用（未接）
}
void beep_off()
{
    // 蜂鸣器暂不使用（未接）
}
