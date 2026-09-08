/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《EC11旋转编码器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ec11.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef EC11_STM32_H
#define EC11_STM32_H

#include <stdint.h>

/* EC11 旋转编码器驱动（stm32 纯驱动，B 类——**仅 stm32 条目，无 mspm0 对照**
 * （地阔星仅有页面；库内无旋转编码器模块），ADR 0009）：
 * - A/B 相 + SW 按键 3 × GPIO 输入上拉（引脚/端口宏单源在 pin_config.h：
 *   EC11_A_GPIO/PIN = PA4、EC11_B_GPIO/PIN = PB5、EC11_SW_GPIO/PIN = PB0——
 *   页面默认 A=PA6/B=PA4/SW=PA7 全被既有角色占用不照抄，同选概率最低推理
 *   见 manifest notes）；
 * - **默认轮询 A/B 相判向（非 EXTI、非 TIMER）**：A 相跳变采样 B 相判向
 *   （页面代码 Encoder_Scanf 原算法——A↑ 时 B 低 = 正转、B 高 = 反转；A↓
 *   镜像；页面 L60-61 真值表与正文 L44-46、代码判向矛盾——**按代码为准**，
 *   notes 记录）；轮询采样窗口/防抖 = **调用方节拍**（页面 TIM3 中断扫描 +
 *   10ms 消抖结构 → 不注册 GPIO EXTI（避开异口同线门禁）、不占 TIMER
 *   （TIM2/3/4 被 PWM/骨架调度占用）；快速旋转两次调用间 A 多跳变会漏计
 *   ——页面定时器扫描同款限制，notes）；
 * - ec11_get_delta() = **增量语义**：返回自上次调用以来的净方向+步数增量
 *   （正 = 顺时针、负 = 逆时针——页面 0/1/2 计数语义归一，每次 A 相跳变 =
 *   1 个方向事件；清零式）——题目常用「旋转 N 格」；
 * - SW 按键：低有效（1=按下），**防抖归调用方节拍**（页面 100ms × 2 分支
 *   阻塞消抖不落——驱动零阻塞）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--ec11.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf——页面
 * printf 在**驱动文件内**（ec11.c L235/255 演示计数函数）必须剔除、函数名
 * 规范化（ec11_init/get_delta/read_sw）、TIM3 中断扫描改轮询、SW 阻塞消抖
 * 改调用方节拍、引脚宏参数化——B 类从零设计）。 */

/* ec11_init：A/B/SW 三脚 GPIO 上拉输入配置（页面 Encoder_GPIO_Init——
 * GPIO_Mode_IPU 等效，ml_gpio IU；页面 TIM3 时钟/中断/NVIC 部分不落
 * ——轮询方案）。 */
void ec11_init(void);

/* ec11_get_delta：返回自上次调用以来的净方向+步数增量（int16_t——正 =
 * 顺时针、负 = 逆时针；0 = 无动作）并清零内部累计。内部 A 相跳变采样 B
 * 相判向（页面代码算法——A 相每跳变 1 次 = 1 个方向事件；哪边正转由 A/B
 * 接线决定——页面 L146「你说的算」）；轮询采样节拍归调用方（10ms 级调度
 * 防抖，快速旋转两次调用间 A 多跳变会漏计）。 */
int16_t ec11_get_delta(void);

/* ec11_read_sw：1=按下、0=松开（SW 低有效——上拉输入接地按下；页面
 * Encoder_Sw_Down 0=未按下/1=按下语义归一）；**防抖归调用方节拍**
 * （页面 delay_ms(100) × 2 分支阻塞消抖不落——调用方 10-20ms 采样即可）。 */
uint8_t ec11_read_sw(void);

#endif /* EC11_STM32_H */
