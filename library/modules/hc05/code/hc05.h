#ifndef HC05_H
#define HC05_H

#include <stdint.h>

/* HC-05 蓝牙串口透传驱动（mspm0 纯驱动，ADR 0009）：
 * - UART 实例 HC05_UART（默认 UART2 共享，9600 8N1——HC05 模块出厂默认
 *   波特率，与其余 UART 实例 115200 互不影响，每个实例独立 targetBaudRate）；
 * - 收发：hc05_send_*（忙等发送）+ RX 中断环形缓冲（hc05_receive 读走，
 *   hc05_available 查询，HC05_RX_BUF_SIZE 溢出丢新字节）；
 * - 连接状态：HC05_STATE 引脚（默认 PA8 输入）——模块 STATE 脚高 = 已连接；
 * - AT 模式切换：HC05_KEY 引脚（默认 PB24 输出）——KEY 拉高后重新上电进入
 *   AT 命令模式（拉低 = 透传模式；运行时切换需断电重启，HC05 硬件行为）。
 * 引脚/极性由母版 syscfg 与宏决定（HC05_STATE_PORT / HC05_STATE_PIN /
 * HC05_KEY_PORT / HC05_KEY_PIN），模块代码零引脚字面量。默认脚与既有模块
 * 刻意重叠（PA23/PA24 = UWB_UART 同 UART2、PA8 = DIGIT_UART TX/IR_BEAM OUT、
 * PB24 = STEP_MOTOR RST2 / SR04 TRIG），同选时经引脚绑定消解（见 manifest notes）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/rf--hc05-bluetooth-module.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 printf/main.c 演示、
 * 函数名规范化、RX 缓冲改环形缓冲、引脚宏参数化、波特率 9600 说明）。 */

#define HC05_RX_BUF_SIZE   128u  /* RX 环形缓冲字节数（2 的幂非必需） */
#define HC05_CONNECTED_LEVEL 1   /* STATE 引脚高电平 = 手机已连接 */

/* hc05_init：SYSCFG_DL_init() 后调用——开 HC05_UART 中断（NVIC）、
 * 复位 RX 缓冲、KEY 引脚置低（透传模式）。 */
void hc05_init(void);

/* 发送（忙等 TX 空闲；发送前不检查连接状态，由调用方决定——见 is_connected） */
void hc05_send_char(uint8_t ch);
void hc05_send_string(const char *str);
void hc05_send_buffer(const uint8_t *buf, uint16_t len);

/* 接收：RX 中断把字节塞入环形缓冲；available = 未读字节数；receive 读走
 * 至多 max_len 字节并返回实际拷贝数（0 = 无数据）。 */
uint16_t hc05_available(void);
uint16_t hc05_receive(uint8_t *buf, uint16_t max_len);
void hc05_clear_rx(void);

/* 连接状态：读 HC05_STATE 引脚（1 = 已连接，0 = 未连接）。 */
uint8_t hc05_is_connected(void);

/* AT 模式切换：at_mode_enter 拉高 KEY（重新上电后进入 AT 命令模式——
 * HC05 硬件要求上电前 KEY 高；程序内无法软切，函数仅驱动引脚电平）； */
void hc05_at_mode_enter(void);
void hc05_at_mode_exit(void);

#endif /* HC05_H */
