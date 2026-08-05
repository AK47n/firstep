/**
 * @file main.c
 * @brief 母版模板 main.c —— MSPM0G3507 最小系统板空工程
 *
 * 确定性模板（非 AI 生成）：时钟初始化 + while(1) 空循环 + TODO 区，
 * 能直接编译烧录。生成器生成工程时用按赛题的骨架 main.c 覆盖本文件。
 */
#include "ti_msp_dl_config.h"

int main(void)
{
    /* 时钟与外设初始化（SysConfig 生成的初始化代码） */
    SYSCFG_DL_init();

    while (1)
    {
        /* TODO: 按赛题在此编写业务逻辑（生成时被按赛题的骨架 main.c 覆盖） */
    }
}
