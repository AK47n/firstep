#include "headfile.h"
#include "uwb_uart.h"
#include "zigbee_uart.h"

// ============================================================
//  中断服务函数
//  C题 — 智能门锁
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

// ---- TIM3: 保留 (未使用) ----
void TIM3_IRQHandler(void)
{
    if (TIM3->SR & 1)
    {
        TIM3->SR &= ~1;
    }
}

// ---- TIM4: 保留 (未使用) ----
void TIM4_IRQHandler(void)
{
    if (TIM4->SR & 1)
    {
        TIM4->SR &= ~1;
    }
}

// ---- USART1: UWB 基站数据接收 ----
void USART1_IRQHandler(void)
{
    // 循环处理所有待接收字节 (RXNE=1 表示有数据)
    while (USART1->SR & 0x20)
    {
        uwb_rx_handler();
    }
    // 溢出错误处理
    if (USART1->SR & 0x08)
    {
        (void)(USART1->DR & 0xFF);  // 读DR清零ORE
    }
}

// ---- USART2/3: 保留 ----
void USART2_IRQHandler(void)
{
    if (USART2->SR & 0x20)
    {
        (void)(USART2->DR & 0xFF);  // 读 DR 清除 RXNE
        // debug_uart_rx_handler();  // 调试命令 (调试时取消注释)
    }
}

// ---- USART3: Zigbee DL-20 钥匙ID接收 ----
void USART3_IRQHandler(void)
{
    // 循环处理所有待接收字节
    while (USART3->SR & 0x20)
    {
        zigbee_rx_handler();
    }
    // 溢出错误处理
    if (USART3->SR & 0x08)
    {
        (void)(USART3->DR & 0xFF);  // 读DR清零ORE
    }
}

// ---- 外部中断 (保留空壳) ----
void EXTI0_IRQHandler(void)
{
    if (EXTI->PR & (1<<0))
        EXTI->PR = 1<<0;
}

void EXTI1_IRQHandler(void)
{
    if (EXTI->PR & (1<<1))
        EXTI->PR = 1<<1;
}

void EXTI2_IRQHandler(void)
{
    if (EXTI->PR & (1<<2))
        EXTI->PR = 1<<2;
}

void EXTI3_IRQHandler(void)
{
    if (EXTI->PR & (1<<3))
        EXTI->PR = 1<<3;
}

void EXTI4_IRQHandler(void)
{
    if (EXTI->PR & (1<<4))
        EXTI->PR = 1<<4;
}

void EXTI9_5_IRQHandler(void)
{
    if (EXTI->PR & (1<<5))
        EXTI->PR = 1<<5;

    if (EXTI->PR & (1<<6))
        EXTI->PR = 1<<6;

    if (EXTI->PR & (1<<7))
        EXTI->PR = 1<<7;

    if (EXTI->PR & (1<<8))
        EXTI->PR = 1<<8;

    if (EXTI->PR & (1<<9))
        EXTI->PR = 1<<9;
}
