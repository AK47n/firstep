/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《红外解码编码模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/Infrared-decoding-coding-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef IR_REMOTE_TX_STM32_H
#define IR_REMOTE_TX_STM32_H

#include <stdint.h>

/* 红外编码发射（stm32，纯驱动切片，ADR 0009）：单 GPIO 直出 38kHz NEC 载波
 * ——`ir_tx_init()` 置空闲低、`ir_tx_send(address, command)` 发完整 NEC 帧
 * （引导码 9ms/4.5ms + 地址/反码/命令/反码 4 字节 + 560us 结束位）、
 * `ir_tx_send_repeat()` 发 NEC 重复码（长按节奏由调用方循环控制——本模块
 * 无状态机）。载波 = CPU 忙等翻转（半周期 **delay_us(13)** ≈13.16us——
 * mspm0 版 delay_cycles(CPUCLK_FREQ/76000) 先例；stm32 无 delay_cycles，
 * delay_us(13) 误差 ±0.5us（载波 ~37.8-38.5kHz），notes 记录），**不占
 * TIMER/PWM**；单帧发射阻塞约 50-90ms（38kHz 位时序全码 1 最坏 ≈86ms）。
 * **API 与 mspm0 ir_remote_tx.h 现名完全对齐**（ir_tx_init / ir_tx_send /
 * ir_tx_send_repeat + IR_TX_FREQ_HZ 38000u + IR_TX_MSB_FIRST 1）。
 * **与批次 1 ir_remote 接收配对**：同一套 NEC 口径（引导 9ms/4.5ms、位低
 * 560us、位高 0=560us/1=1680us、重复码 9ms/2.25ms、反码校验、字节内位序
 * MSB 先——ir_remote 的解码阈值按 20us 拍全部落在本发射脉宽中央），
 * 发射端 + 接收端同选即插即用；默认脚刻意错开（发射 PA9 / 接收 PA10），
 * 双选默认不撞。
 * 引脚 = pin_config.h 宏 IR_TX_PORT / IR_TX_OUT_PIN（输出，默认 PA9——与
 * 视觉/数传链路（DIGIT/COORD/UWB UART1 族）默认重叠、同选概率最低；初始
 * 空闲低）。硬件注意：红外发射管需串限流电阻（100-200Ω）、5V 供电；MCU
 * GPIO 3.3V 驱动能力有限（~8-16mA），发射距离不足时加三极管/MOS 驱动。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/rf--Infrared-decoding-coding-module.md
 * （立创 wiki 地阔星移植手册；页面是「MCU+发射头+接收头、UART 指令」模块
 * 形态——5 字节串口指令（帧头 A1/通用 FA + 操作位 F1 发射/F2 改地址/F3 改
 * 波特率 + 反馈）解析归生成骨架（ADR 0009），本模块只出 NEC 发射原语；
 * 代码按模块库规范改写：去 main/printf、函数名规范化、F1 标准库 GPIO/USART
 * API 换算 ml_gpio/ml_delay）。 */

#define IR_TX_FREQ_HZ 38000u /* NEC 载波 38kHz（半周期 13.16us） */

/* 字节内位序：1 = MSB 先（与库内 ir_remote 批次 1 解码口径一致，收发配对
 * 必须保持）；标准 NEC 协议为 LSB 先——控制市售设备（电视/空调遥控对拷）
 * 时改为 0 并重新编译。 */
#define IR_TX_MSB_FIRST 1

/* ir_tx_init：发射脚置空闲低电平（载波关）。 */
void ir_tx_init(void);

/* ir_tx_send：发一帧 NEC 数据（地址 + 命令，各带反码校验位）；阻塞
 * 约 50-90ms（38000Hz 忙等，视位密度）。 */
void ir_tx_send(uint8_t address, uint8_t command);

/* ir_tx_send_repeat：发 NEC 重复码（9ms 载波 + 2.25ms 空闲 + 560us 载波）；
 * 按键长按时的连续重复由调用方按节奏循环（标准间隔 ~110ms）。 */
void ir_tx_send_repeat(void);

#endif /* IR_REMOTE_TX_STM32_H */
