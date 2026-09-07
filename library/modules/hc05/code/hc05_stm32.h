/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《HC05蓝牙模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/hc05-bluetooth-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef HC05_STM32_H
#define HC05_STM32_H

#include <stdint.h>

/* HC-05 蓝牙串口透传驱动（stm32，纯驱动，ADR 0009）：
 * - **API 与 mspm0 hc05.h 现名完全对齐**（同名/同语义）：hc05_init /
 *   hc05_send_char|string|buffer（忙等发送）+ RX 中断环形缓冲
 *   （hc05_receive 读走、hc05_available 查询、hc05_clear_rx 清空，
 *   HC05_RX_BUF_SIZE 溢出丢新字节）+ hc05_is_connected 读 STATE 引脚
 *   （HC05_CONNECTED_LEVEL=1 = 已连接）+ hc05_at_mode_enter|exit 驱动
 *   KEY 引脚（拉高 + 重新上电进 AT——HC05 硬件行为，程序内无法软切）；
 * - **UART 实例仲裁**：默认 **UART_1（UWB_UART 宿主，TX=PA9/RX=PA10）**——
 *   蓝牙手机遥控与 UWB 室内定位链路**互替件**、同选概率最低（mspm0 定稿
 *   HC05 与 UWB 同外设共享先例；stm32 的 UWB = UART_1 → 同款推理挂 UART_1）；
 *   默认与 DIGIT/COORD/K230 视觉链路并列共享（默认×默认共享 = 合法先例、
 *   `_check_uart_instance_conflicts` 只查用户绑定），同选时经引脚绑定换实例
 *   成对消解；F1 页默认串口2（PA2/PA3 = DEBUG_UART 常备件）不照抄；
 * - 9600 8N1 透传（HC05 模块出厂默认——独立于其余 115200 角色，
 *   `uart_baud_config` 逐实例配置；页面代码 115200 与 AT 默认 38400 不一，
 *   mspm0 已定 9600，沿）；
 * - 引脚/极性由 pin_config.h 宏与值决定（HC05_UART/INST + STATE/KEY
 *   `_GPIO/_PIN`），模块代码零引脚字面量；**RX 中断聚合归母版 isr.c**
 *   （USARTx_IRQHandler → pin_config.h `USART1_IRQ_CALLS` 聚合宏 →
 *   hc05_rx_handler——pinwriter `_UART_CALLS_ROLES` 已登记，main.c 勿写
 *   USART1_IRQHandler）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/rf--hc05-bluetooth-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 printf/main.c 演示、
 * 函数名规范化、RX 缓冲改环形缓冲、引脚宏参数化、F1 标准库 USART 与 GPIO
 * API 换算 ml_uart/ml_gpio）。 */

#define HC05_RX_BUF_SIZE   128u  /* RX 环形缓冲字节数（照 mspm0 HC05_RX_BUF_SIZE） */
#define HC05_CONNECTED_LEVEL 1   /* STATE 引脚高电平 = 手机已连接 */
#define HC05_BAUDRATE      9600  /* HC05 出厂默认波特率（透传模式） */

/* hc05_init：UART 引脚/实例初始化（uart_pin_init_ex 参数化）+ 9600、
 * STATE 输入上拉、KEY 输出推挽置低（透传模式）、复位 RX 缓冲。
 * uart_pin_init_ex 已使能 RX 中断（本件 RX = 中断环形缓冲，需要）。 */
void hc05_init(void);

/* 发送（uart_sendbyte 忙等 TX 完成；发送前不检查连接状态，由调用方决定） */
void hc05_send_char(uint8_t ch);
void hc05_send_string(const char *str);
void hc05_send_buffer(const uint8_t *buf, uint16_t len);

/* 接收：hc05_rx_handler（isr.c 聚合调用）把字节塞入环形缓冲；
 * available = 未读字节数；receive 读走至多 max_len 字节并返回实际拷贝数
 * （0 = 无数据）；clear_rx 清空。 */
uint16_t hc05_available(void);
uint16_t hc05_receive(uint8_t *buf, uint16_t max_len);
void hc05_clear_rx(void);

/* 连接状态：读 HC05_STATE 引脚（1 = 已连接，0 = 未连接）。 */
uint8_t hc05_is_connected(void);

/* AT 模式切换：at_mode_enter 拉高 KEY（重新上电后进入 AT 命令模式——
 * HC05 硬件要求上电前 KEY 高；程序内无法软切，函数仅驱动引脚电平）；
 * at_mode_exit 拉低（透传模式）。 */
void hc05_at_mode_enter(void);
void hc05_at_mode_exit(void);

/* RX 中断处理（母版 isr.c 经 USART1_IRQ_CALLS 聚合调用——勿在 main.c 定义） */
void hc05_rx_handler(void);

#endif /* HC05_STM32_H */
