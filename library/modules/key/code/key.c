#include "key.h"

/* 按键读取（纯驱动，ADR 0009）：上拉输入，低电平 = 按下。
 * 编码器计数已迁至 motor 模块。 */

uint8_t get_key_state(uint32_t key) {
    uint32_t high_bits = DL_GPIO_readPins(KEY_PORT, key);
    if((high_bits & key) == 0) return 1;  // 上拉：低电平=按下
    else return 0;
}
