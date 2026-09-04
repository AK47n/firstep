#include "ir_beam_mspm0.h"
#include "ti_msp_dl_config.h"

/* 红外对射传感器读取（mspm0 纯驱动）：三线制 VCC/GND/OUT，
 * OUT → IR_BEAM_PORT / IR_BEAM_OUT_PIN（母版 syscfg 实例 IR_BEAM，
 * 默认 PA8——仅与 DIGIT_UART 默认重叠，同选时经引脚绑定消解）。
 * 极性：内部上拉输入——无遮挡 = 低电平（接收管导通拉低），
 * 遮挡 = 高电平（开集输出截止，上拉钳位）。实际模块极性相反时改
 * IR_BEAM_BLOCKED_LEVEL 一处即可。 */

#define IR_BEAM_BLOCKED_LEVEL 1 /* 遮挡时的引脚电平（1=高，0=低） */

void ir_beam_init(void)
{
    /* SysConfig 已把 IR_BEAM 配成输入（SYSCFG_DL_init 生效），无需逐脚初始化。 */
}

uint8_t ir_beam_read(void)
{
    uint32_t bits = DL_GPIO_readPins(IR_BEAM_PORT, IR_BEAM_OUT_PIN);
    uint8_t level = (bits & IR_BEAM_OUT_PIN) ? 1 : 0;
    return (level == IR_BEAM_BLOCKED_LEVEL) ? 1 : 0; /* 1=遮挡，0=无遮挡 */
}
