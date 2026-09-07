/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《红外接收模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/infrared-receiving-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef IR_REMOTE_STM32_H
#define IR_REMOTE_STM32_H

#include <stdint.h>

/* 红外遥控接收解码驱动（stm32，纯驱动，ADR 0009）：NEC 协议（38kHz 载波
 * 接收头输出直接接 GPIO——无信号 = 高电平、有信号 = 低电平脉冲）。
 * - **API 与 mspm0 ir_remote.h 现名完全对齐**：ir_remote_init /
 *   ir_remote_poll（1 = 新帧解码成功、2 = 重复码、0 = 超时/无效帧）/
 *   ir_remote_get_address / ir_remote_get_code / ir_remote_has_data /
 *   ir_remote_clear；
 * - 解码：ir_remote_poll() 阻塞等待引导码（9ms 低 + 4.5ms 高），CPU 忙等按
 *   20us 步进测量位脉宽（560us 级），**不占 TIMER**（stm32 TIM 全被
 *   PWM/编码器/调度占用——照 mspm0 TIMG 全占先例；立创原版在 EXTI
 *   下降沿中断内同步解码整帧，本库改主循环轮询——EXTI 聚合/编码器独占
 *   先例（ir_beam 轮询先例），轮询与中断解码行为等价（同步忙等
 *   ~10ms 等待 + ~50ms 解码/帧）；
 * - 输出：地址码 + 命令码（校验：地址/命令各带反码，~a==a' && ~c==c'
 *   才有效——页面 `infrared_data_true_judgment` 反码判断逻辑错乱修正，
 *   mspm0 同）；重复码（9ms 低 + 2.5ms 高）单独以返回值 2 报告。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/rf--infrared-receiving-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 printf/main.c 演示、
 * 函数名规范化、引脚宏参数化、F1 标准库 GPIO/EXTI 换算 ml_gpio、EXTI 中断
 * 改轮询、页面数据错乱判断修正——见 notes）。 */

/* ir_remote_init：复位解码状态（引脚配置由 init 完成——gpio_init 上拉输入）。 */
void ir_remote_init(void);

/* ir_remote_poll：阻塞等一帧。返回 1 = 新帧解码成功（get_address/get_code
 * 可取）；2 = 收到重复码（上一帧代码不变）；0 = 超时/无效帧。单次调用忙等
 * 至多 ~10ms（等待信号）+ 解码期 ~50ms（有信号时）。 */
uint8_t ir_remote_poll(void);

/* 最近一次有效帧的地址/命令码（反码校验后；重复码不改写） */
uint8_t ir_remote_get_address(void);
uint8_t ir_remote_get_code(void);

/* 1 = 有未消费的新帧/重复码；clear 后归 0 */
uint8_t ir_remote_has_data(void);
void ir_remote_clear(void);

#endif /* IR_REMOTE_STM32_H */
