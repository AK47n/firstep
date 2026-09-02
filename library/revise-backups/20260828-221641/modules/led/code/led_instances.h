/* led_instances.h —— 生成器多实例渲染产物（module-multi-instance/03）：LED 通道宏 + 每通道 (port, pin) 表。改接线改这里（stm32：直接改 GPIO_x/Pin_y 对；mspm0：改 syscfg 的 $assign）。 */
#ifndef _led_instances_h_
#define _led_instances_h_

#define LED_CHANNEL_COUNT 1

// 通道索引（led_init/led_on/led_off/led_toggle 的 channel 实参；两平台一致：RED=0 / YELLOW=1 / GREEN=2 / LED_1=3 …；越界自动钳回首通道）
#define LED_RED      0

// 每通道 (port, pin)：驱动读 LED_PIN_TABLE 建表
#define LED_CHANNEL_0_PORT LED_BEEP_PORT
#define LED_CHANNEL_0_PIN  LED_BEEP_LED_PIN

#define LED_PIN_TABLE { {LED_CHANNEL_0_PORT, LED_CHANNEL_0_PIN} }

// 便捷控制宏（LED 一脚接地、另一脚接 MCU 引脚：拉电流接法，led_on = 亮）
#define LED_RED_ON()     led_on(LED_RED)
#define LED_RED_OFF()    led_off(LED_RED)
#endif
