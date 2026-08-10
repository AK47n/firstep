#include "pid.h"
#include "motor_stm32.h"

// 10ms 周期定时中断：编码器读数进速度闭环（21F user/isr.c 原样提取，
// 真机编译过）。TIM3 需在 main.c 里用 ml_tim 的 tim_interrupt_ms_init
// 配置为 10ms 周期中断（选 pid 即带本调度，闭环开箱即用）。
void TIM3_IRQHandler(void)
{
    if (TIM3->SR & 1)
    {
        // 读取编码器速度（10ms 内脉冲数），关闭全局中断防止竞态
        __disable_irq();
        int enc1 = Encoder_count1;
        int enc2 = Encoder_count2;
        Encoder_count1 = 0;
        Encoder_count2 = 0;
        __enable_irq();
        motorA.now = (float)enc1;
        motorB.now = (float)enc2;

        pid_control();

        TIM3->SR &= ~1;
    }
}
