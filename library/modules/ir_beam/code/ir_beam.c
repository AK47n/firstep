#include "ir_beam.h"
#include "pin_config.h"
#include "headfile.h"

/* 红外对射传感器读取（stm32 纯驱动，ADR 0009）：三线制 VCC/GND/OUT，
 * OUT → IR_BEAM_GPIO/IR_BEAM_PIN（pin_config.h 单源，默认 PA8）。
 * 极性：内部上拉输入（IU）——无遮挡 = 低电平（接收管导通拉低），
 * 遮挡 = 高电平（上拉钳位，与库内载物在位检测同法）。实际模块极性
 * 相反时改 IR_BEAM_BLOCKED_LEVEL 一处即可。 */

#define IR_BEAM_BLOCKED_LEVEL 1 /* 遮挡时的引脚电平（1=高，0=低） */

void ir_beam_init(void)
{
    gpio_init(IR_BEAM_GPIO, IR_BEAM_PIN, IU); /* 内部上拉输入 */
}

uint8_t ir_beam_read(void)
{
    uint8_t level = gpio_get(IR_BEAM_GPIO, IR_BEAM_PIN) ? 1 : 0;
    return (level == IR_BEAM_BLOCKED_LEVEL) ? 1 : 0; /* 1=遮挡，0=无遮挡 */
}
