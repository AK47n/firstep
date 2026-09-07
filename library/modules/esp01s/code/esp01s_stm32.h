/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《ESP-01S WiFi模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/esp01s-wifi-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef ESP01S_STM32_H
#define ESP01S_STM32_H

#include <stdint.h>

/* ESP-01S WiFi 模块驱动（stm32 纯驱动，B 类——仅 stm32 条目、无 mspm0
 * 对照，ADR 0009）：
 * - **真实串口 115200 + AT 指令透传**（页面代码形态）：esp01s_send_cmd
 *   发送 AT 行（自动补 \r\n）+ 有界应答匹配（命中 "OK" 返回 1、超时/非
 *   OK 返回 0——页面 WIFI_Send_Cmd 原式简化：去 goto 改 for/while、去
 *   ack 参数——**AT 模板（CWMODE/CWSAP/CIPSERVER/CIPSEND/MQTT*）归骨架/
 *   范围外**（与 as32「AT 配置范围外」先例同构：模板 = 应用层，模块只出
 *   串口透传原语）；MQTT/阿里云/JSON/hmacsha1 demo 明确范围外（密钥/固件
 *   绑定）；
 * - **RX 线性缓冲**：esp01s_rx_handler（母版 isr.c USARTx_IRQHandler →
 *   pin_config.h `USART1_IRQ_CALLS` 聚合宏调用——pinwriter
 *   `_UART_CALLS_ROLES` 已登记，main.c 勿写 USARTx_IRQHandler）逐字节入
 *   缓冲（ESP01S_RX_BUF_SIZE 上限 + 按长度 NUL 终结）；**缺陷修正**：
 *   ① 页面 `(len+1)%200` 环形回绕覆盖首字节 → 本件线性缓冲 + 超限截断
 *   （丢弃新字节）；② 页面 IDLE 中断在当前位写 `'\0'` 断串错位 → 本件
 *   按长度终结（无 IDLE 依赖）；③ 页面 `while(test[i++]!=':')` 无界扫 →
 *   本件有界扫描；④ 页面 buff[50] 截断 200 字节数据 → 本件缓冲上限
 *   ESP01S_RX_BUF_SIZE（200）+ out 按 max 截断；
 * - `esp01s_parse_ipd`：`+IPD,<id>,<len>:<data>` 帧识别原语化（+IPD 定位/
 *   id/len 有界解析 + 载荷按 max 截断）；
 * - 页面发数据（AT+CIPSEND 等 `">"` 等待）归骨架（AT 模板范围外）；
 *   页面 L44 提示 MQTT AT 需烧 MQTT 固件——notes 记录（模块只透传，固件
 *   准备归用户）。
 * 引脚/极性由 pin_config.h 宏与值决定（ESP01S_UART/INST/TX/RX `_GPIO/_Pin`），
 * 模块代码零引脚字面量；默认 **UART_1（PA9/PA10）**——与 HC05 手机遥控
 * **互替件同脚先例**（ESP-01S 手机/上位机遥控与 HC05 蓝牙 = 同手机遥控链路），
 * 同选经引脚绑定换实例成对消解。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/rf--esp01s-wifi-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：中断缓冲改线性截断 +
 * 有界扫描、Send_Cmd 原语化（去 goto/ack/printf）、去 MQTT/JSON demo、
 * 函数名规范化、引脚宏参数化）。 */

#define ESP01S_RX_BUF_SIZE     200u  /* 页面 WIFI_RX_LEN_MAX 200（上限截断保护） */
#define ESP01S_CMD_TIMEOUT_MS  1000u /* send_cmd 应答等待超时（页面 waitms 原式） */
#define ESP01S_BAUDRATE        115200 /* ESP-01S 出厂默认（页面） */

/* esp01s_init：UART 引脚/实例初始化（uart_pin_init_ex 参数化）+ 115200、
 * 复位 RX 缓冲。uart_pin_init_ex 已使能 RX 中断（本件 RX = 中断收缓冲，需要）。 */
void esp01s_init(void);

/* 发送 AT 指令行（cmd + "\r\n"）+ 等待应答：命中 "OK" 返回 1；超时/未命中/
 * 应答为 ERROR 返回 0（页面 WIFI_Send_Cmd 原式——去 ack/goto 参数化；
 * 发前清 RX 缓冲防陈旧匹配；每条命令后建议 receive 读走应答）。 */
uint8_t esp01s_send_cmd(const char *cmd);

/* 透传发送（原样字符串——如 AT+CIPSEND 后负载；不追加换行）。 */
void esp01s_send_string(const char *s);

/* 缓冲有数据（1/0）。 */
uint8_t esp01s_available(void);

/* 读走应答：拷至多 max_len 字节（截断保护）+ 清空缓冲；返回实际拷贝数。 */
uint16_t esp01s_receive(uint8_t *buf, uint16_t max_len);

/* +IPD 帧解析：从 RX 缓冲识别 `+IPD,<id>,<len>:<data>`（有界扫描——页面
 * 无界扫修正），载荷拷到 out（至多 max 字节、NUL 终结）。返回 0 = 解析成功
 * （id/len 出参 = 客户端号/实际拷贝字节数）；非 0 = 无 +IPD 帧/格式异常。 */
uint8_t esp01s_parse_ipd(uint8_t *id, uint16_t *len, uint8_t *out, uint16_t max);

/* RX 中断处理（母版 isr.c 经 USART1_IRQ_CALLS 聚合调用——勿在 main.c 定义） */
void esp01s_rx_handler(void);

#endif /* ESP01S_STM32_H */
