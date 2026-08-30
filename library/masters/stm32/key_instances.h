/* key_instances.h —— 按键通道宏 + 每通道 (port, pin) 表（生成器多实例渲染产物，
 * key-multi-instance/03）。选中 key 且带实例清单时生成器按实例计划覆写本文件
 * （工程根、与 pin_config.h 同级）；本文件 = 单实例默认：1 通道，引脚取
 * pin_config.h（接线单源——改板载按键引脚只改 pin_config.h）。 */
#ifndef _key_instances_h_
#define _key_instances_h_

#define KEY_CHANNEL_COUNT 1

// 通道索引（get_key_state 的 channel 实参；两平台一致：KEY_START=0 /
// KEY_STOP=1 / KEY_MODE=2 / KEY_SET=3 / KEY_1=4 …；越界自动钳回首通道——
// 单实例默认下 STOP/MODE/SET/KEY_1 均与首通道同脚，行为与 led 单通道别名一致）
#define KEY_START 0
#define KEY_STOP  1
#define KEY_MODE  2
#define KEY_SET   3
#define KEY_1     4

// 每通道 (port, pin)：key_stm32.c 读 KEY_PIN_TABLE 建表（KEY_GPIO / KEY_PIN
// 由 pin_config.h 定义）
#define KEY_CHANNEL_0_GPIO KEY_GPIO
#define KEY_CHANNEL_0_PIN  KEY_PIN

#define KEY_PIN_TABLE { {KEY_CHANNEL_0_GPIO, KEY_CHANNEL_0_PIN} }

#endif
