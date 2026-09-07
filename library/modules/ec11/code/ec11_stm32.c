/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《EC11旋转编码器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ec11.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ec11_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* EC11 旋转编码器（stm32 纯驱动，B 类——仅 stm32 条目）：
 * - 轮询 A/B 相判向（页面 Encoder_Scanf 算法）：只在 A 相跳变时采样 B 相
 *   （页面原文「当A发生跳变时采集B当前的状态」）——A↑ 时 B=低 = 正转、
 *   B=高 = 反转；A↓ 镜像。页面 L60-61 真值表（同沿=顺时针）与正文
 *   L44-46、代码判向矛盾——按代码为准确认；**哪边正转由 A/B 接线决定**
 *   （页面 L146「哪一边正转哪一边反转不需要太在意，你说的算」）；
 * - **不注册 EXTI、不占 TIMER**：页面 TIM3 定时器中断扫描（注释 10ms/
 *   实际 5ms——PSC 3600-1/ARR 100）改调用方节拍轮询（取样窗口 10ms 级
 *   调度防抖；TIM2/3/4 被 PWM/骨架调度占用——定时器实例冲突门禁）；
 * - 增量语义：每次 A 相跳变 ±1 累计到静态增量，ec11_get_delta 返回自
 *   上次调用以来的净增量并清零（题目常用「旋转 N 格」——每格对应 2 次
 *   A 相边沿（一格半脉冲/两格整脉冲，页面 L50-52），真机标定留后续）；
 * - SW 低有效，防抖归调用方节拍（页面 100ms 阻塞消抖不落——驱动零阻塞）。 */

static uint8_t ec11_prev_a = 1;   /* A 相上次电平（上拉输入默认高） */
static int16_t ec11_accum = 0;    /* 自上次清零以来的净增量（方向+步数） */

void ec11_init(void)
{
    gpio_init(EC11_A_GPIO, EC11_A_PIN, IU);  /* A 相（页面 LCK/CLK）上拉输入 */
    gpio_init(EC11_B_GPIO, EC11_B_PIN, IU);  /* B 相（页面 DT）上拉输入 */
    gpio_init(EC11_SW_GPIO, EC11_SW_PIN, IU);/* SW 上拉输入（按下接地低） */
}

int16_t ec11_get_delta(void)
{
    uint8_t a = gpio_get(EC11_A_GPIO, EC11_A_PIN) ? 1 : 0;
    uint8_t b;
    int16_t delta = 0;

    if (a != ec11_prev_a) { /* A 相跳变 → 采样 B 相判向（页面算法） */
        b = gpio_get(EC11_B_GPIO, EC11_B_PIN) ? 1 : 0;
        if (a) { /* A 上升沿：B=低 = 正转（+1）、B=高 = 反转（-1） */
            delta = b ? -1 : 1;
        } else { /* A 下降沿：B=低 = 反转（-1）、B=高 = 正转（+1） */
            delta = b ? 1 : -1;
        }
        ec11_prev_a = a;
        ec11_accum = (int16_t)(ec11_accum + delta);
    }
    /* 清零式增量语义：返回自上次调用以来的净增量 */
    delta = ec11_accum;
    ec11_accum = 0;
    return delta;
}

uint8_t ec11_read_sw(void)
{
    /* SW 低有效：上拉输入按下接地低电平 → 1=按下（页面 Encoder_Sw_Down
     * 0=未按下/1=按下语义归一）；防抖归调用方节拍 */
    return gpio_get(EC11_SW_GPIO, EC11_SW_PIN) ? 0 : 1;
}
