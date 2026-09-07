/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AS32-LoRa无线通信模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/as32-lora-wireless-communication-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef AS32_STM32_H
#define AS32_STM32_H

#include <stdint.h>

/* AS32-TTL-100 433MHz LoRa 无线数传模块驱动（stm32，纯驱动切片，ADR 0009）：
 * 真实 UART 双向透传——**API 与 mspm0 as32.h 现名完全对齐**（同名/同语义/
 * 同返回码）：as32_send_string/send_hex 发送、as32_receive 轮询收数（返回
 * 字节数、读后清缓冲）、as32_flush 清接收缓冲。
 * **UART 实例仲裁**：默认 UART_3（ZIGBEE_UART 宿主，TX=PB10/RX=PB11——
 * ZIGBEE_UART 原脚）——LoRa 与 Zigbee 无线数传**互替件**、同选概率最低
 * （mspm0 定稿同款：默认挂 UART3、同选时经引脚绑定换实例/换脚消解；
 * 注意 `_check_uart_instance_conflicts` 只查用户绑定——默认×默认共享 =
 * 合法先例，与 UWB/DIGIT/COORD 共 UART_1 现状同口径；as32×zigbee_uart
 * 同选默认 = UART_3 双消费者 → 经绑定成对换位消解，interrupt 接收与轮询
 * 共享实例时轮询方收不到字节——互替件同选概率最低、绑定消解）。
 * **轮询接收**：uart_pin_init_ex 后关闭 RXNEIE（CR1 bit5）——页面
 * USART2 接收中断+空闲中断缓冲改轮询（mspm0 同判：轮询避免与同实例
 * zigbee_uart 的 ISR 强符号重复；stm32 侧再免去 isr.c 聚合表登记；
 * RX 排空 = SR RXNE 位直读 → DR，与 coord_detect 先例同款）。
 * **截断保护修正**：页面 LOAR_RX_LEN=(LOAR_RX_LEN+1)%LOAR_RX_LEN_MAX
 * 模运算在满缓冲回绕覆盖首字节——本件改 cap 截断（满则丢新字节 + '\0'
 * 收尾），notes 记录。
 * **AT 配置不落码**（页面无 AT 指令代码——「参数的修改是通过上位机进行
 * 设置」+ MD0/MD1 硬件模式，页面驱动未接线）：AT 指令模板与 MD0/MD1
 * 模式脚**范围外**——需要 AT 配置时可经 as32_send_string 在配置模式下直发
 * （M0/M1 脚由用户接线）或上位机 soft_asds.zip 预配置后再透传（notes）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/rf--as32-lora-wireless-communication-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、引脚宏参数化、页面接收中断改轮询、F1 标准库 USART_* 换算 ml_uart）。 */

/* 接收缓冲上限（页面 LOAR_RX_LEN_MAX 原值 300——照 mspm0 AS32_RX_BUF_MAX） */
#define AS32_RX_BUF_MAX 300u

/* AS32 波特率 9600（页面「默认波特率 9600」+ AS32 出厂默认——独立于其余
 * 115200 串口角色，uart_baud_config 逐实例配置） */
#define AS32_BAUDRATE 9600

/* as32_init：UART 引脚/实例初始化（uart_pin_init_ex 参数化 = 绑定换脚随
 * pin_config.h 宏）+ 9600 + **关 RXNEIE（轮询——页面接收中断改轮询）** +
 * 清接收状态。 */
void as32_init(void);

/* as32_send_string：发送字符串（NUL 结尾；页面 LOAR_USART_send_String——
 * uart_sendbyte 忙等 TC 后逐字节）。 */
void as32_send_string(const char *str);

/* as32_send_hex：发送二进制数据（页面 LOAR_USART_send_HEX，len 字节）。 */
void as32_send_hex(const uint8_t *data, uint16_t len);

/* as32_receive：轮询排空 RX 收数据（页面 Anakysis_Data「读到即清」语义 +
 * 中断缓冲改轮询）。返回本次取到的字节数（0 = 当前无数据）；buf 拷入
 * max_len-1 字节以内（截断保护 + '\0' 收尾——页面模运算回绕修正）；**读后
 * 缓冲即清**（buf 传 NULL/max_len==0 同样清空——读空即消费，页面语义）。 */
uint16_t as32_receive(uint8_t *buf, uint16_t max_len);

/* as32_flush：清接收缓冲（页面 Clear_LOAR_RX_BUFF 语义——数据+长度+标志
 * 全清，调用后未读数据丢弃）。 */
void as32_flush(void);

#endif /* AS32_STM32_H */
