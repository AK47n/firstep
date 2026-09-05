#ifndef IR_REMOTE_H
#define IR_REMOTE_H

#include <stdint.h>

/* 红外遥控接收解码驱动（mspm0 纯驱动，ADR 0009）：NEC 协议（38kHz 载波接收头
 * 输出直接接 GPIO——无信号 = 高电平、有信号 = 低电平脉冲）。
 * - 解码：ir_remote_poll() 阻塞等待引导码（9ms 低 + 4.5ms 高），CPU 忙等按
 *   20us 步进测量位脉宽（560us 级），不占 TIMER（地猛星 TIMG 全占，sr04 先例；
 *   立创原版在 GROUP1_IRQHandler 内同步解码整帧，本库改主循环轮询——MSPM0
 *   全部 GPIO 中断共用 GROUP1 一个向量且被 motor 编码器独占，红外+电机是
 *   经典组合、无法共存第二个 GROUP1_IRQHandler，轮询解码与中断解码行为等价
 *   （同步忙等 ~50ms/帧））；
 * - 输出：地址码 + 命令码（校验：地址/命令各带反码，~a==a' && ~c==c' 才有效）；
 *   重复码（9ms 低 + 2.5ms 高）单独以返回值 2 报告。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/rf--infrared-receiving-module.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 printf/main.c 演示、
 * 函数名规范化、引脚宏参数化、GROUP1 中断改轮询、数据错乱判断修正——原版
 * infrared_data_true_judgment 反码判断逻辑错乱见 notes）。 */

/* ir_remote_init：复位解码状态（syscfg 已配 IR_REMOTE 输入，无需外设动作）。 */
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

#endif /* IR_REMOTE_H */
