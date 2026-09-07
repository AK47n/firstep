/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《4x4矩阵键盘》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/4x4-keyboard.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "key_matrix_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 4×4 矩阵键盘（stm32 纯驱动，B 类——仅 stm32 条目）：
 * - 行列扫描（页面 key_scan 原式）：逐行拉低（低电平有效）→ 扫 4 列
 *   （!gpio_get = 该行列键按下）→ 键值 i×4+j+1（行主序 1-16、0=无键）→
 *   恢复行高 → 命中即整扫退出（多键同时按只返回首个——页面 behavior）；
 * - 行列跨端口逐脚宏族（KEY_MATRIX_ROWn_GPIO/PIN + COLn_GPIO/PIN——
 *   pin_config.h 单源：ROW=PB12/13/14/15、COL=PA9/PA10/PB10/PB11）；
 * - 无防抖/连按/释放语义（页面无防抖代码、main 500ms 演示节拍会丢键——
 *   防抖归调用方节拍：10-20ms 采样 + 两次确认 + 沿检测）；
 * - 页面串台（记录不落码）：L22「更改为 bsp_mh100x.c 与 bsp_mh100x.h」vs
 *   L39 #include "bsp_matrixkey.h"（文件名不一致；h 宏 _BSP_MATRIXKEY_H_
 *   又对齐 matrixkey——mh100x 为他件名残留）。 */

static void key_matrix_row_set(uint8_t row, uint8_t level)
{
    /* 逐行输出（宏族逐脚——行列跨端口，无共享端口宏） */
    switch (row) {
    case 0:
        gpio_set(KEY_MATRIX_ROW1_GPIO, KEY_MATRIX_ROW1_PIN, level);
        break;
    case 1:
        gpio_set(KEY_MATRIX_ROW2_GPIO, KEY_MATRIX_ROW2_PIN, level);
        break;
    case 2:
        gpio_set(KEY_MATRIX_ROW3_GPIO, KEY_MATRIX_ROW3_PIN, level);
        break;
    default:
        gpio_set(KEY_MATRIX_ROW4_GPIO, KEY_MATRIX_ROW4_PIN, level);
        break;
    }
}

static uint8_t key_matrix_col_get(uint8_t col)
{
    /* 逐列输入（宏族逐脚——返回 1 = 引脚高/未按下、0 = 引脚低/按下） */
    switch (col) {
    case 0:
        return gpio_get(KEY_MATRIX_COL1_GPIO, KEY_MATRIX_COL1_PIN) ? 1 : 0;
    case 1:
        return gpio_get(KEY_MATRIX_COL2_GPIO, KEY_MATRIX_COL2_PIN) ? 1 : 0;
    case 2:
        return gpio_get(KEY_MATRIX_COL3_GPIO, KEY_MATRIX_COL3_PIN) ? 1 : 0;
    default:
        return gpio_get(KEY_MATRIX_COL4_GPIO, KEY_MATRIX_COL4_PIN) ? 1 : 0;
    }
}

void key_matrix_init(void)
{
    /* 4 行推挽输出（页面 Out_PP + 50MHz）+ 4 列上拉输入（页面 IPU）；
     * 行初始置高（页面未显式置位——复位 ODR=0 行低会误选第 0 行，初始
     * 置高后行为与页面首次扫描后一致，等价无回归） */
    gpio_init(KEY_MATRIX_ROW1_GPIO, KEY_MATRIX_ROW1_PIN, OUT_PP);
    gpio_init(KEY_MATRIX_ROW2_GPIO, KEY_MATRIX_ROW2_PIN, OUT_PP);
    gpio_init(KEY_MATRIX_ROW3_GPIO, KEY_MATRIX_ROW3_PIN, OUT_PP);
    gpio_init(KEY_MATRIX_ROW4_GPIO, KEY_MATRIX_ROW4_PIN, OUT_PP);
    gpio_init(KEY_MATRIX_COL1_GPIO, KEY_MATRIX_COL1_PIN, IU);
    gpio_init(KEY_MATRIX_COL2_GPIO, KEY_MATRIX_COL2_PIN, IU);
    gpio_init(KEY_MATRIX_COL3_GPIO, KEY_MATRIX_COL3_PIN, IU);
    gpio_init(KEY_MATRIX_COL4_GPIO, KEY_MATRIX_COL4_PIN, IU);
    key_matrix_row_set(0, 1);
    key_matrix_row_set(1, 1);
    key_matrix_row_set(2, 1);
    key_matrix_row_set(3, 1);
}

uint8_t key_matrix_scan(void)
{
    uint8_t i;
    uint8_t j;
    uint8_t key_val = 0;

    for (i = 0; i < KEY_MATRIX_ROWS; i++) {
        /* 选中第 i 行（低电平有效） */
        key_matrix_row_set(i, 0);

        /* 检测列的状态，确定按键是否被按下 */
        for (j = 0; j < KEY_MATRIX_COLS; j++) {
            /* 如果该列被拉低（列被行低拉低 = 该行该列键按下） */
            if (key_matrix_col_get(j) == 0) {
                /* 计算按键编号（页面原式：行主序 1-16、0=无键） */
                key_val = (uint8_t)(i * 4 + j + 1);
                break;
            }
        }

        /* 恢复该行的输出状态 */
        key_matrix_row_set(i, 1);

        /* 如果按键被按下，则直接退出扫描（页面 behavior——多键只返回首个） */
        if (key_val) {
            break;
        }
    }
    return key_val;
}
