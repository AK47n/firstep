/* key_instances.h —— 按键通道宏 + 每通道 (port, pin) 表（生成器多实例渲染产物，
 * key-multi-instance/03）。选中 key 且带实例清单时生成器按实例计划覆写本文件
 * （key.c 同目录，随模块复制进工程）；本文件 = 单实例默认：地猛星板载键
 * （PA2，KEY 组——改引脚改 syscfg 不改这里）。 */
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

// 每通道 (port, pin)：key.c 读 KEY_PIN_TABLE 建表（KEY_PORT / KEY_START_PIN
// 由 SysConfig 按 mspm0.syscfg 生成——实例名 KEY、引脚名 START）
#define KEY_CHANNEL_0_PORT KEY_PORT
#define KEY_CHANNEL_0_PIN  KEY_START_PIN

#define KEY_PIN_TABLE { {KEY_CHANNEL_0_PORT, KEY_CHANNEL_0_PIN} }

#endif
