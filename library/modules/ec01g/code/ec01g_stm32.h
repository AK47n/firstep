/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《EC-01G NB-IoT+GPS模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/ec01g-nbiot-gps-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef EC01G_STM32_H
#define EC01G_STM32_H

#include <stdint.h>

/* EC-01G NB-IoT+GPS 模块驱动（stm32 纯驱动，B 类——仅 stm32 条目、无 mspm0
 * 对照，ADR 0009）：
 * - **真实串口 9600 + AT 指令透传底座**（页面代码形态）：ec01g_send_cmd
 *   发送 AT 行（自动补 \r\n）+ 有界应答匹配（命中 "OK" 返回 1、超时/非
 *   OK 返回 0——页面 EC01G_Send_Cmd 原式：去 goto/ack 参数化）；
 *   ec01g_send_string 透传负载、available/receive 读走应答；
 * - **页面 NB-IoT HTTP 天气 demo（Seniverse_Init/Get_Weather_Data/hex 解码/
 *   JSON 解析/Search_Data）归范围外**（心知天气密钥/城市宏/API 字符串 =
 *   应用层；模块只出 AT 底座原语——esp01s「AT 模板范围外」同口径）；
 *   **页面无 GPS 代码**（NB-IoT+GPS 模块但 demo 仅 HTTP 天气）——GPS 功能
 *   （若需）按官方资料 AT 指令集（docs.ai-thinker.com）另议或复用 neo_6m
 *   模块，notes 记录；
 * - **RX 线性缓冲**：ec01g_rx_handler（母版 isr.c USARTx_IRQHandler →
 *   pin_config.h `USART3_IRQ_CALLS` 聚合宏调用——pinwriter
 *   `_UART_CALLS_ROLES` 已登记，main.c 勿写 USARTx_IRQHandler）逐字节入
 *   缓冲（EC01G_RX_BUF_SIZE 上限 + 按长度 NUL 终结）；**缺陷修正**：
 *   ① 页面 Get_Weather_Data 超时后 `rev_buff=NULL→+=11` **空指针崩溃** →
 *   本件无 HTTP 状态指针（模块只透传）+ 入参 `NULL` 检查守卫；
 *   ② 页面 Search_Data `while(!='"')` 无界扫 + 补零位错 `[i+1]` → 本件
 *   JSON/天气解析整体不落（范围外），AT 匹配/扫描全部有界；
 *   ③ 页面 `(LEN+1)%2096` 环形回绕 + IDLE `'\0'` → 本件线性缓冲 +
 *   超限截断（丢弃新字节）+ 按长度终结；页面缓冲 2096 为 HTTP hex 响应
 *   预留——本件 256（AT 透传场景符合；HTTP 响应解析范围外，若骨架做
 *   HTTP 需自行扩大/分帧）。
 * 引脚/极性由 pin_config.h 宏与值决定（EC01G_UART/INST/TX/RX `_GPIO/_Pin`），
 * 模块代码零引脚字面量；默认 **UART_3（PB10/PB11）**——NB-IoT 蜂窝无线与
 * Zigbee/LoRa 无线链路**互替件同脚先例**（无线链路二选一接入），同选经
 * 引脚绑定换实例成对消解。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/rf--ec01g-nbiot-gps-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：AT 底座原语化（去
 * goto/ack/printf）、HTTP 天气/JSON/hex 解码 demo 剔除、中断缓冲改线性
 * 截断、函数名规范化、引脚宏参数化）。 */

#define EC01G_RX_BUF_SIZE     256u  /* AT 应答缓冲（页面 2096 为 HTTP 预留——本件透传够用） */
#define EC01G_CMD_TIMEOUT_MS  1000u /* send_cmd 应答等待超时（页面 waitms 原式） */
#define EC01G_BAUDRATE        9600  /* EC-01G 出厂默认（页面；注释「ESP01S 9600」串台已纠正） */

/* ec01g_init：UART 引脚/实例初始化（uart_pin_init_ex 参数化）+ 9600、
 * 复位 RX 缓冲。uart_pin_init_ex 已使能 RX 中断（本件 RX = 中断收缓冲，需要）。 */
void ec01g_init(void);

/* 发送 AT 指令行（cmd + "\r\n"）+ 等待应答：命中 "OK" 返回 1；超时/未命中/
 * 应答为 ERROR 返回 0（页面 EC01G_Send_Cmd 原式——去 ack/goto 参数化；
 * cmd 为 NULL 直接返回 0——空指针保护；发前清 RX 缓冲防陈旧匹配）。 */
uint8_t ec01g_send_cmd(const char *cmd);

/* 透传发送（原样字符串——如 AT+HTTP... 负载；不追加换行；NULL 安全）。 */
void ec01g_send_string(const char *s);

/* 缓冲有数据（1/0）。 */
uint8_t ec01g_available(void);

/* 读走应答：拷至多 max_len 字节（截断保护）+ 清空缓冲；返回实际拷贝数。 */
uint16_t ec01g_receive(uint8_t *buf, uint16_t max_len);

/* RX 中断处理（母版 isr.c 经 USART3_IRQ_CALLS 聚合调用——勿在 main.c 定义） */
void ec01g_rx_handler(void);

#endif /* EC01G_STM32_H */
