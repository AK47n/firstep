#ifndef IR_BEAM_H
#define IR_BEAM_H

#include <stdint.h>

/* 红外对射传感器读取（stm32，纯驱动，ADR 0009）：1=遮挡（光束被挡住），
 * 0=无遮挡。引脚单源在 pin_config.h：IR_BEAM_GPIO / IR_BEAM_PIN（默认 PA8）。
 * 极性宏 IR_BEAM_BLOCKED_LEVEL 定义在 ir_beam.c（当前 1 = 遮挡为高电平）。 */

void ir_beam_init(void);
uint8_t ir_beam_read(void);

#endif // IR_BEAM_H
