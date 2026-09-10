/*
 * 2024H（车载平衡滚球运动控制系统）· mspm0 母版空 main
 *
 * A6 真机验收（ascii-project-name/01 #03）用：只验「生成到桌面 → 目录名 ASCII
 * → gmake 全量编译 exit=0 → 产出 .out」这条链路，不验赛题逻辑，故与母版
 * 模板 main.c 等价（SYSCFG_DL_init 注释掉：母版空 main 的调用不在模块头接口集
 * 里，生成门禁会判未定义——骨架阶段的产物本来就带 TODO 注释形态）。
 */
#include "ti_msp_dl_config.h"

int main(void)
{
    /* TODO: 若使用 SysConfig 生成的外设初始化，请取消下面注释 */
    // SYSCFG_DL_init();

    while (1) {
    }
}
