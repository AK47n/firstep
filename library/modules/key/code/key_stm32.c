#include "key_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 按键读取（stm32 纯驱动，ADR 0009）：上拉输入，低电平 = 按下。
 * 通道表见 key_instances.h（KEY_CHANNEL_COUNT + KEY_PIN_TABLE——生成器多实例
 * 渲染产物；默认 = 单实例 1 通道 KEY_GPIO/KEY_PIN，pin_config.h 单源，默认
 * PB3——JTDO，SWD 调试用不到，复位后即普通 GPIO）。key_init() 逐通道配置
 * 内部上拉输入（IU），上拉低电平按下。 */

typedef struct {
    GPIOn_enum port;
    Pinx_enum pin;
} key_pin_t;

static const key_pin_t KEY_PINS[KEY_CHANNEL_COUNT] = KEY_PIN_TABLE;

void key_init(void)
{
    uint8_t i;
    for (i = 0; i < KEY_CHANNEL_COUNT; i++) {
        gpio_init(KEY_PINS[i].port, KEY_PINS[i].pin, IU); // 内部上拉输入
    }
}

uint8_t get_key_state(uint8_t channel)
{
    if (channel >= KEY_CHANNEL_COUNT) {
        channel = 0; // 越界钳回首通道（key_instances.h 契约）
    }
    return gpio_get(KEY_PINS[channel].port, KEY_PINS[channel].pin) ? 0 : 1; // 低电平 = 按下
}
