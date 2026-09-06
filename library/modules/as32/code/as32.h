#ifndef AS32_H
#define AS32_H

#include <stdint.h>

/* AS32-TTL-100 433MHz LoRa 无线数传模块驱动（mspm0，纯驱动切片，ADR 0009）：
 * 真实 UART 双向透传（独立实例 AS32_UART，UART3 默认、9600、**轮询接收**——
 * 不注册 UART 中断、无 ISR 强符号，fingerprint/open_mv4「裁剪后独占」先例）。
 * as32_send_string/send_hex 发送（DL_UART_isBusy 忙等 + 逐字节）、
 * as32_receive 轮询排空 RX FIFO → 模块内缓冲（≤max_len-1 截断 + '\0'）→
 * 一次性返回并清缓冲（页面 Anakysis_Data「读到即清」语义）；
 * as32_flush 清接收缓冲（页面 Clear_LOAR_RX_BUFF 语义）。
 * 引脚 = 母版 syscfg 实例 AS32_UART：TX（默认 PA26）/RX（默认 PA25——真实
 * UART 外设引脚，宏 AS32_UART_INST；与 ZIGBEE_UART 同 UART3 外设同脚：
 * LoRa 与 Zigbee 无线数传**互替件**、同选概率最低——单选裁剪后独占 UART3，
 * 同选时经引脚绑定换实例/换脚消解；OPENMV4_UART×DIGIT_UART 同构先例；
 * 与 HUIDU R1（PA26）/L4（PA25）默认重叠同选时消解）。
 * 页面语义保留（页面 LOAR_USART_send_String/HEX、Anakysis_Data、
 * Clear_LOAR_RX_BUFF、LOAR_RX_LEN_MAX 300）：透传字符串收发、**无帧结构**
 * ——行分帧/校验归调用方骨架（ADR 0009）；页面 UART_1_INST_IRQHandler
 * 接收中断缓冲改造为轮询排空（open_mv4「IRQHandler 随轮询裁剪」先例）；
 * **截断保护修正**：页面 LOAR_RX_LEN=(LOAR_RX_LEN+1)%LOAR_RX_LEN_MAX
 * 模运算在满缓冲回绕覆盖首字节——本件改 cap 截断（满则丢新字节 + '\0'
 * 收尾），notes 记录。
 * **AT 配置不落码**（页面无 AT 指令代码——「参数的修改是通过上位机进行
 * 设置」+ MD0/MD1 硬件模式，页面驱动未接线）：AT 指令模板与 MD0/MD1
 * 模式脚**范围外**——需要 AT 配置时可经 as32_send_string 在配置模式下直发
 * （M0/M1 脚由用户接线）或上位机 soft_asds.zip 预配置后再透传（notes 写明）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/rf--as32-lora-wireless-communication-module.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、NVIC 随轮询裁剪、IRQHandler 改轮询、全局收敛模块静态）。 */

/* 接收缓冲上限（页面 LOAR_RX_LEN_MAX 原值 300） */
#define AS32_RX_BUF_MAX 300u

/* as32_init：清接收状态（页面 LOAR_Init 的 NVIC 清除/使能段随轮询裁剪——
 * 无中断接收无需中断线；UART 引脚/波特率由 SYSCFG_DL_init() 配置）。 */
void as32_init(void);

/* as32_send_string：发送字符串（NUL 结尾；页面 LOAR_USART_send_String
 * 原样——逐字节 DL_UART_isBusy 忙等 + DL_UART_Main_transmitData）。 */
void as32_send_string(const char *str);

/* as32_send_hex：发送二进制数据（页面 LOAR_USART_send_HEX 原样，len 字节）。 */
void as32_send_hex(const uint8_t *data, uint16_t len);

/* as32_receive：轮询排空 RX FIFO 收数据（页面 Anakysis_Data「读到即清」
 * 语义 + 中断缓冲改轮询）。返回本次取到的字节数（0 = 当前无数据）；buf 拷入
 * max_len-1 字节以内（截断保护 + '\0' 收尾——页面模运算回绕修正）；**读后
 * 缓冲即清**（buf 传 NULL/max_len==0 同样清空——读空即消费，页面语义）。 */
uint16_t as32_receive(uint8_t *buf, uint16_t max_len);

/* as32_flush：清接收缓冲（页面 Clear_LOAR_RX_BUFF 语义——数据+长度+标志
 * 全清，调用后未读数据丢弃）。 */
void as32_flush(void);

#endif /* AS32_H */
