#include "led.h"
#include "ti_msp_dl_config.h"

/* 地猛星用户 LED（PA15，LED_BEEP 组）：灌电流接法，低电平点亮。
 * 板载 PA0/PA1 被 I2C0（MPU6050）占用，不作用户 LED。 */

void led_init(uint8_t channel)
{
    (void)channel; // 单通道：SysConfig 已把 LED_BEEP_LED 配置为输出
    led_off(channel);
}

void led_on(uint8_t channel)
{
    (void)channel;
    DL_GPIO_clearPins(LED_BEEP_PORT, LED_BEEP_LED_PIN); // 低电平点亮
}

void led_off(uint8_t channel)
{
    (void)channel;
    DL_GPIO_setPins(LED_BEEP_PORT, LED_BEEP_LED_PIN); // 高电平熄灭
}

void led_toggle(uint8_t channel)
{
    (void)channel;
    DL_GPIO_togglePins(LED_BEEP_PORT, LED_BEEP_LED_PIN);
}
