#include "key.h"
#include "ti_msp_dl_config.h"

/* 按键读取（纯驱动，ADR 0009）：上拉输入，低电平 = 按下。
 * 通道表见 key_instances.h（KEY_CHANNEL_COUNT + KEY_PIN_TABLE——生成器多实例
 * 渲染产物；单实例默认 1 通道 PA2，KEY 组）。编码器计数已迁至 motor 模块。 */

typedef struct {
    GPIO_Regs *port;
    uint32_t pin_mask;
} key_pin_t;

static const key_pin_t KEY_PINS[KEY_CHANNEL_COUNT] = KEY_PIN_TABLE;

void key_init(void)
{
    /* SysConfig 已把各通道配置为输入（多实例 = 各自 GPIO 输入实例），
     * SYSCFG_DL_init 生效，无需逐通道初始化。 */
}

uint8_t get_key_state(uint8_t channel)
{
    if (channel >= KEY_CHANNEL_COUNT) {
        channel = 0; // 越界钳回首通道（key_instances.h 契约）
    }
    key_pin_t key = KEY_PINS[channel];
    uint32_t bits = DL_GPIO_readPins(key.port, key.pin_mask);
    return (bits & key.pin_mask) == 0 ? 1 : 0; // 上拉：低电平 = 按下
}
