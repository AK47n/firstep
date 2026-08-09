/**
 * @file main.c
 * @brief 母版模板 main.c —— STM32F103C8T6 最小系统板空工程
 *
 * 确定性模板（非 AI 生成）：时钟初始化 + while(1) 空循环 + TODO 区，
 * 能直接编译烧录。生成器生成工程时用按赛题的骨架 main.c 覆盖本文件。
 *
 * 头文件只依赖 stm32f10x.h（寄存器操作风格：SystemInit 声明在
 * system_stm32f10x.h:79，stm32f10x.h:479 已 include 它；本模板只用
 * stm32f10x.h 无条件部分，不依赖 USE_STDPERIPH_DRIVER / conf.h 机制——
 * 工单 09 决策 8）。
 */
#include "stm32f10x.h"

int main(void)
{
    /* 时钟初始化：配置 72MHz 主频（启动文件已调用 SystemInit，此处显式调用确保时钟就绪） */
    SystemInit();

    while (1)
    {
        /* TODO: 按赛题在此编写业务逻辑（生成时被按赛题的骨架 main.c 覆盖） */
    }
}
