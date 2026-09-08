/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《4x4矩阵键盘》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/4x4-keyboard.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef KEY_MATRIX_STM32_H
#define KEY_MATRIX_STM32_H

#include <stdint.h>

/* 4×4 矩阵键盘驱动（stm32 纯驱动，B 类——**仅 stm32 条目，无 mspm0 对照**
 * （地阔星仅有页面；库内无矩阵键盘模块），ADR 0009）：
 * - 8 脚宏族（pin_config.h 单源——行列跨端口、逐脚端口宏，照批 2 UART 先例）：
 *   行输出 ROW1-4 = PB12/13/14/15（低有效拉低——叠 DIP0-3+GRAY_D1-4+ttp224：
 *   **互替件同脚先例**——机械键盘与触摸 4 键互替、二选一接入）、列输入
 *   COL1-4 = PA9/PA10/PB10/PB11（上拉——叠 DIGIT/COORD/UWB UART +
 *   ZIGBEE UART：键盘与视觉/数传链路不同框）；
 * - 扫描 = 逐行拉低扫列（页面原式）：选中第 i 行（低电平有效）→ 扫 4 列
 *   （列被拉低 = 该行该列键按下）→ 键值 **i×4+j+1**（行主序 1-16、0=无键）
 *   → 恢复行高 → 命中即整扫退出（页面 behavior——多键同时按只返回首个）；
 * - **防抖/连按/释放语义归调用方节拍**（页面无防抖代码、main 500ms 演示
 *   节拍会丢键——不落；调用方 10-20ms 采样 + 两次确认 + 沿检测即可）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--4x4-keyboard.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化（key_matrix_init/scan）、8 脚宏参数化（页面 port_row/port_col 数组
 * 全 GPIOA ——不照抄，行列跨端口逐脚宏）、页面 L22「bsp_mh100x.c/.h」与
 * L39 include「bsp_matrixkey.h」文件名串台——notes 记录）。 */

/* 行数 / 列数（页面 4×4 原值——宏族逐脚：KEY_MATRIX_ROWn_GPIO/PIN +
 * KEY_MATRIX_COLn_GPIO/PIN，16 宏） */
#define KEY_MATRIX_ROWS 4u
#define KEY_MATRIX_COLS 4u

/* key_matrix_init：8 脚 GPIO 配置——4 行推挽输出（OUT_PP，初始高——页面
 * MatrixKey_GPIO_Init 未显式置位行脚（复位 ODR=0 → 初始化后行低 = 首扫
 * 「第 0 行被迫选中」，实现补初始置高：行为等价无回归）+ 4 列上拉输入
 * （IU——页面 GPIO_Mode_IPU），时钟由 ml_gpio 内部完成。 */
void key_matrix_init(void);

/* key_matrix_scan：扫描 4×4 矩阵，返回键值——0 = 无键、1-16 = 对应键
 * （行主序：第 i 行第 j 列 = i×4+j+1——页面原式；无物理键位映射表，键面
 * 字符图由调用方/接线决定）；**防抖/连按/释放语义不在此**——调用方按
 * 10-20ms 节拍采样 + 沿检测（驱动零阻塞）。 */
uint8_t key_matrix_scan(void);

#endif /* KEY_MATRIX_STM32_H */
