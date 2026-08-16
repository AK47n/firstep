#include "key_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 按键读取（stm32 纯驱动）：引脚宏 KEY_GPIO / KEY_PIN 由 pin_config.h
 * 单源（key 模块引脚声明渲染，默认 PB3——JTDO，SWD 调试用不到，复位后
 * 即普通 GPIO）。上拉输入，低电平 = 按下。 */

uint8_t get_key_state(void)
{
    return gpio_get(KEY_GPIO, KEY_PIN) ? 0 : 1; // 低电平 = 按下
}
