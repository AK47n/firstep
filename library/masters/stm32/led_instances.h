/* led_instances.h —— LED 通道宏 + 每通道 (port, pin) 表（生成器多实例渲染产物，
 * module-multi-instance/03）。选中 led 且带实例清单时生成器按实例计划覆写本文件
 * （工程根、与 pin_config.h 同级）；本文件 = 单实例默认：三通道 PC13/14/15，
 * 引脚取 pin_config.h（接线单源——改板载 LED 引脚只改 pin_config.h）。 */
#ifndef _led_instances_h_
#define _led_instances_h_

#define LED_CHANNEL_COUNT 3

// 通道索引（led_init/led_on/led_off/led_toggle 的 channel 实参；两平台一致：
// RED=0 / YELLOW=1 / GREEN=2 / LED_1=3 …；越界自动钳回首通道）
#define LED_RED     0
#define LED_YELLOW  1
#define LED_GREEN   2

// 每通道 (port, pin)：ml_led.c 读 LED_PIN_TABLE 建表
#define LED_CHANNEL_0_PORT LED_PORT
#define LED_CHANNEL_0_PIN  LED_RED_PIN
#define LED_CHANNEL_1_PORT LED_PORT
#define LED_CHANNEL_1_PIN  LED_YELLOW_PIN
#define LED_CHANNEL_2_PORT LED_PORT
#define LED_CHANNEL_2_PIN  LED_GREEN_PIN

#define LED_PIN_TABLE { {LED_CHANNEL_0_PORT, LED_CHANNEL_0_PIN}, {LED_CHANNEL_1_PORT, LED_CHANNEL_1_PIN}, {LED_CHANNEL_2_PORT, LED_CHANNEL_2_PIN} }

// 便捷控制宏（LED 一脚接地、另一脚接 MCU 引脚：拉电流接法，led_on = 亮）
#define LED_RED_ON()     led_on(LED_RED)
#define LED_RED_OFF()    led_off(LED_RED)
#define LED_YELLOW_ON()  led_on(LED_YELLOW)
#define LED_YELLOW_OFF() led_off(LED_YELLOW)
#define LED_GREEN_ON()   led_on(LED_GREEN)
#define LED_GREEN_OFF()  led_off(LED_GREEN)

#endif
