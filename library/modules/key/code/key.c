#include "key.h"

uint8_t get_key_state(uint32_t key) {
    uint32_t high_bits = DL_GPIO_readPins(KEY_PORT, key);
    if((high_bits & key) == 0) return 1;  // 上拉：低电平=按下
    else return 0;
}

// 电机编码器计数（由 GPIO 中断驱动，motor.c extern 引用）：
//   counter_1_A — 电机1编码器（DC_MOTOR_AA_PORT 组，DC_MOTOR_AA_IIDX）
//   counter_2_A — 电机2编码器（DC_MOTOR_BA_PORT 组，DC_MOTOR_BA_IIDX）
// GPIO 组走 syscfg 生成的 DC_MOTOR_AA/BA_PORT 宏（DC_MOTOR 组 associatedPins
// AA=PA16→GPIOA、BA=PB19→GPIOB；改接线只改母版 mspm0.syscfg 的 $assign）。
uint32_t counter_1_A = 0;
uint32_t counter_2_A = 0;

void GROUP1_IRQHandler()
{
    switch (DL_GPIO_getPendingInterrupt(DC_MOTOR_BA_PORT))
    {
    case DC_MOTOR_BA_IIDX:
        /* code */
        counter_2_A ++;
        break;

    default:
        break;
    }

    switch (DL_GPIO_getPendingInterrupt(DC_MOTOR_AA_PORT))
    {
    case DC_MOTOR_AA_IIDX:
        /* code */
        counter_1_A ++;
        break;

    default:
        break;
    }

}
