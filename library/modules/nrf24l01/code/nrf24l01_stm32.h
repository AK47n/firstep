/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《NRF24L01无线2.4G模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/nrf24l01-2-4-g-control-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef NRF24L01_STM32_H
#define NRF24L01_STM32_H

#include <stdint.h>

/* NRF24L01 2.4G 无线收发驱动（stm32，纯驱动，ADR 0009）：
 * - **软 SPI 位操作**：CLK/MOSI/CSN/CE 输出 + MISO/IRQ 输入（6 × GPIO，
 *   **不占硬件 SPI 外设/TIMER**——页面硬件 SPI1（9MHz）改 GPIO 位操作；
 *   默认全端口 B（单 `NRF24L01_PORT` 共享端口宏，同口约束照 ttp224 先例）；
 *   mspm0 先例位操作零延时（NRF 规格 ≤10MHz，72MHz GPIO 翻转达标，notes）；
 * - **API 与 mspm0 nrf24l01.h 现名完全对齐**：nrf24l01_init /
 *   set_channel / set_speed / set_power / set_address / set_mode /
 *   tx_packet / rx_packet / flush_rx / flush_tx + 枚举/返回码/PAYLOAD_MAX；
 * - 收发：tx_packet 写 T载入 → CE 脉冲发送（忙等 IRQ 引脚，500ms 超时）；
 *   rx_packet 轮询 STATUS 的 RX_DR 位（**IRQ 脚只读状态，不注册 GPIO
 *   中断**——EXTI 聚合/编码器独占先例，按页面「轮询方式接收」实现；
 *   CPU 忙等期间不占 TIMER）；
 * - 上游缺陷处理：页内 `#if DYNAMIC_PACKET==0` 分支引用页外
 *   L01_WriteSingleReg（上游残留 bug）——整枝剔除，动态包长归一为 1
 *   （mspm0 同）；页内多处误把 FLUSH 命令当寄存器地址——改用显式 flush。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/rf--nrf24l01-2-4-g-control-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：硬件 SPI 驱动改软 SPI
 * 位操作、30+ 函数收敛为库风格子集、去掉 printf/main.c 演示、引脚宏参数化、
 * F1 标准库 GPIO/SPI API 换算 ml_gpio）。 */

typedef enum {
    NRF24L01_MODE_TX = 0,   /* 发射（PRIM_RX=0） */
    NRF24L01_MODE_RX        /* 接收（PRIM_RX=1） */
} nrf24l01_mode_t;

typedef enum {
    NRF24L01_SPEED_250K = 0,
    NRF24L01_SPEED_1M,
    NRF24L01_SPEED_2M
} nrf24l01_speed_t;

typedef enum {
    NRF24L01_POWER_M18DBM = 0,
    NRF24L01_POWER_M12DBM,
    NRF24L01_POWER_M6DBM,
    NRF24L01_POWER_0DBM
} nrf24l01_power_t;

/* 返回值 = STATUS 寄存器位（页内定义保留）：TX 完成 / 达最大重发 / RX 就绪 */
#define NRF24L01_TX_OK   0x20
#define NRF24L01_MAX_TX  0x10
#define NRF24L01_RX_OK   0x40
#define NRF24L01_TX_ERR  0xFF  /* 其它原因发送失败（超时等） */

#define NRF24L01_PAYLOAD_MAX 32  /* 单包最大字节数 */

/* nrf24l01_init：初始化射频（默认地址 0x34,0x43,0x10,0x10,0x01、信道 0、
 * 1M 速率、0dBm 功率、P0 自动应答 + 动态包长；CE 拉高 = 上电）。 */
void nrf24l01_init(void);

/* 配置（init 后若要改默认值再调用；地址最大 5 字节，TX/RX P0 同址） */
void nrf24l01_set_channel(uint8_t channel);       /* 0-127（0x00-0x7F） */
void nrf24l01_set_speed(nrf24l01_speed_t speed);
void nrf24l01_set_power(nrf24l01_power_t power);
void nrf24l01_set_address(const uint8_t *addr, uint8_t len);

/* 模式切换：TX / RX（RX 后需轮询 rx_packet 取数据） */
void nrf24l01_set_mode(nrf24l01_mode_t mode);

/* 发送：len ≤ 32；返回 NRF24L01_TX_OK / NRF24L01_MAX_TX / NRF24L01_TX_ERR。 */
uint8_t nrf24l01_tx_packet(const uint8_t *buf, uint8_t len);

/* 接收：轮询 STATUS——无数据返回 0；有数据读走（≤ max_len）并清 RX FIFO，
 * 返回实际字节数。调用方循环轮询（IRQ 脚与 STATUS 位同源）。 */
uint8_t nrf24l01_rx_packet(uint8_t *buf, uint8_t max_len);

/* 手动清收发 FIFO（异常恢复用；rx_packet/tx_packet 内部已各自清） */
void nrf24l01_flush_rx(void);
void nrf24l01_flush_tx(void);

#endif /* NRF24L01_STM32_H */
