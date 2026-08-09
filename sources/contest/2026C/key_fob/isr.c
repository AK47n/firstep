#include "headfile.h"

// ============================================================
//  中断服务函数 — 数字钥匙端
// ============================================================

// ---- TIM2: 1ms 系统滴答 ----
void TIM2_IRQHandler(void)
{
    if (TIM2->SR & 1)
    {
        g_systick++;
        TIM2->SR &= ~1;
    }
}

// ---- TIM3/4: 保留 ----
void TIM3_IRQHandler(void)
{
    if (TIM3->SR & 1)
    {
        TIM3->SR &= ~1;
    }
}

void TIM4_IRQHandler(void)
{
    if (TIM4->SR & 1)
    {
        TIM4->SR &= ~1;
    }
}

// ---- USART1: 保留 (Zigbee DL-20 只发不收，中断未开启) ----
void USART1_IRQHandler(void)
{
    if (USART1->SR & 0x20)
    {
        (void)(USART1->DR & 0xFF);
    }
}

// ---- USART2/3: 未使用 ----
void USART2_IRQHandler(void)
{
    if (USART2->SR & 0x20)
    {
        (void)(USART2->DR & 0xFF);
    }
}

void USART3_IRQHandler(void)
{
    if (USART3->SR & 0x20)
    {
        (void)(USART3->DR & 0xFF);
    }
}
