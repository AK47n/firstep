/* led_instances.h —— LED 通道宏 + 每通道 (port, pin) 表（生成器多实例渲染产物，
 * module-multi-instance/03）。选中 led 且带实例清单时生成器按实例计划覆写本文件
 * （led.c 同目录，随模块复制进工程）；本文件 = 单实例默认：地猛星 1 个用户 LED
 * （PA15，LED_BEEP 组——改引脚改 syscfg 不改这里）。 */
#ifndef _led_instances_h_
#define _led_instances_h_

#define LED_CHANNEL_COUNT 1

// 通道索引（led_init/led_on/led_off/led_toggle 的 channel 实参；两平台一致：
// RED=0 / YELLOW=1 / GREEN=2 / LED_1=3 …；越界自动钳回首通道——单实例下
// YELLOW/GREEN 仍指 PA15，与旧三别名同脚行为一致）
#define LED_RED     0
#define LED_YELLOW  1
#define LED_GREEN   2

// 每通道 (port, pin)：led.c 读 LED_PIN_TABLE 建表（LED_BEEP 宏由 SysConfig
// 按 mspm0.syscfg 生成）
#define LED_CHANNEL_0_PORT LED_BEEP_PORT
#define LED_CHANNEL_0_PIN  LED_BEEP_LED_PIN

#define LED_PIN_TABLE { {LED_CHANNEL_0_PORT, LED_CHANNEL_0_PIN} }

// 便捷控制宏（LED 一脚接地、另一脚接 MCU 引脚：拉电流接法，led_on = 亮）
#define LED_RED_ON()     led_on(LED_RED)
#define LED_RED_OFF()    led_off(LED_RED)
#define LED_YELLOW_ON()  led_on(LED_YELLOW)
#define LED_YELLOW_OFF() led_off(LED_YELLOW)
#define LED_GREEN_ON()   led_on(LED_GREEN)
#define LED_GREEN_OFF()  led_off(LED_GREEN)

#endif
