#include "ttp224.h"
#include "ti_msp_dl_config.h" /* TTP224_PORT / TTP224_OUT1-4_PIN
                                * （SysConfig 生成命名：<实例>_<引脚名>_PIN；
                                * 四脚同 GPIOA 单 TTP224_PORT 宏，
                                * NRF24L01 先例——输入脚读值不需 IOMUX） */

/* TTP224 4 路电容触摸按键（mspm0 纯驱动）：页面 4 个 Key_IN1-4_Scanf 收敛为
 * read(channel)/read_all；极性单点反相宏 TTP224_TOUCH_LEVEL（页面 = 高电平
 * 触摸；TTP224N 实物若低有效改 0 即可）。 */

static uint8_t ttp224_raw_level(uint8_t channel)
{
    uint32_t bits;

    switch (channel) {
    case 1:
        bits = DL_GPIO_readPins(TTP224_PORT, TTP224_OUT1_PIN) & TTP224_OUT1_PIN;
        break;
    case 2:
        bits = DL_GPIO_readPins(TTP224_PORT, TTP224_OUT2_PIN) & TTP224_OUT2_PIN;
        break;
    case 3:
        bits = DL_GPIO_readPins(TTP224_PORT, TTP224_OUT3_PIN) & TTP224_OUT3_PIN;
        break;
    case 4:
        bits = DL_GPIO_readPins(TTP224_PORT, TTP224_OUT4_PIN) & TTP224_OUT4_PIN;
        break;
    default:
        return 0; /* 通道越界（页面无 5+ 键） */
    }
    return bits ? 1 : 0;
}

void ttp224_init(void)
{
    /* GPIO 输入（内部上拉）由 SYSCFG_DL_init() 配置，无需运行时初始化 */
}

uint8_t ttp224_read(uint8_t channel)
{
    uint8_t level = ttp224_raw_level(channel);
    return (level == TTP224_TOUCH_LEVEL) ? 1 : 0;
}

uint8_t ttp224_read_all(void)
{
    uint8_t mask = 0;
    uint8_t ch;

    for (ch = 1; ch <= TTP224_CHANNELS; ch++) {
        if (ttp224_read(ch)) {
            mask |= (uint8_t)(1u << (ch - 1));
        }
    }
    return mask;
}
