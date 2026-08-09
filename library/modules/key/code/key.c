#include "key.h"

uint8_t get_key_state(uint32_t key) {
    uint32_t high_bits = DL_GPIO_readPins(KEY_PORT, key);
    if((high_bits & key) == 0) return 1;  // 上拉：低电平=按下
    else return 0;
}

// 电机编码器计数（由 GPIO 中断驱动，motor.c extern 引用）：
//   counter_1_A — 电机1编码器（GPIOA 组，DC_MOTOR_AA_IIDX = DIO16）
//   counter_2_A — 电机2编码器（GPIOB 组，DC_MOTOR_BA_IIDX）
uint32_t counter_1_A = 0;
uint32_t counter_2_A = 0;

void GROUP1_IRQHandler()
{
    switch (DL_GPIO_getPendingInterrupt(GPIOB))
    {
    case DC_MOTOR_BA_IIDX:
        /* code */
        counter_2_A ++;
        break;

    default:
        break;
    }

    switch (DL_GPIO_getPendingInterrupt(GPIOA))
    {
    case DC_MOTOR_AA_IIDX:
        /* code */
        counter_1_A ++;
        break;

    default:
        break;
    }

}
