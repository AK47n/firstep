#ifndef IR_BEAM_MSPM0_H
#define IR_BEAM_MSPM0_H

#include <stdint.h>

/* 红外对射传感器读取（mspm0，纯驱动，ADR 0009）：1=遮挡（光束被挡住），
 * 0=无遮挡。引脚 = 母版 syscfg 实例 IR_BEAM / 引脚 OUT（默认 PA8，内部
 * 上拉，与 stm32 侧同脚）。极性宏 IR_BEAM_BLOCKED_LEVEL 定义在
 * ir_beam_mspm0.c（当前 1 = 遮挡为高电平）。 */

void ir_beam_init(void);
uint8_t ir_beam_read(void);

#endif // IR_BEAM_MSPM0_H
