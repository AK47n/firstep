#include "ml_systick.h"
#include "system_stm32f10x.h"

volatile uint32_t g_systick = 0;

void systick_init(void)
{
    SysTick_Config(SystemCoreClock / 1000);  // 1ms 节拍中断
}

void SysTick_Handler(void)
{
    g_systick++;
}
