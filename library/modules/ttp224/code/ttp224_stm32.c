/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《TTP224触摸传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ttp224-touch-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ttp224_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* TTP224 4 路电容触摸按键（stm32 纯驱动）：页面 4 个 Key_IN1-4_Scanf 收敛为
 * read(channel)/read_all（mspm0 批次先例）；极性单点反相宏
 * TTP224_TOUCH_LEVEL（页面 = 高电平触摸；TTP224N 实物若低有效改 0 即可）。
 * 引脚下拉输入（页面原式 GPIO_Mode_IPD → ml_gpio 的 **ID**——与 mspm0 版
 * 上拉 IU 差异：模块推挽输出，上下拉不影响判定，notes 记录平台差异与理由）；
 * 页面 L85 GPIO_ResetBits 对输入脚冗余（IPD 已含下拉），不保留。
 * 页面杂项（记录不修正）：正文器件描述为 TTP223B（单路点动型）——标题/
 * 采购/代码均为 TTP224（4 路），文案串台；规格「100Ms」（应为 ms）、
 * 「GOIO」（应为 GPIO）拼写误；页面 L32「GOIO」控制方式。 */

static uint8_t ttp224_raw_level(uint8_t channel)
{
    switch (channel) {
    case 1:
        return gpio_get(TTP224_GPIO, TTP224_OUT1_PIN) ? 1 : 0;
    case 2:
        return gpio_get(TTP224_GPIO, TTP224_OUT2_PIN) ? 1 : 0;
    case 3:
        return gpio_get(TTP224_GPIO, TTP224_OUT3_PIN) ? 1 : 0;
    case 4:
        return gpio_get(TTP224_GPIO, TTP224_OUT4_PIN) ? 1 : 0;
    default:
        return 0; /* 通道越界（页面无 5+ 键） */
    }
}

void ttp224_init(void)
{
    gpio_init(TTP224_GPIO, TTP224_OUT1_PIN, ID);
    gpio_init(TTP224_GPIO, TTP224_OUT2_PIN, ID);
    gpio_init(TTP224_GPIO, TTP224_OUT3_PIN, ID);
    gpio_init(TTP224_GPIO, TTP224_OUT4_PIN, ID);
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
