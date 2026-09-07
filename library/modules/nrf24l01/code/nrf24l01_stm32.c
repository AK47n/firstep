/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《NRF24L01无线2.4G模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/nrf24l01-2-4-g-control-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "nrf24l01_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* NRF24L01 2.4G 无线收发（stm32 纯驱动，软 SPI 位操作）：
 * 页内硬件 SPI（drv_spi.c 的 SPI1_*）改 GPIO 位操作（CLK/MOSI/MISO 走
 * NRF24L01 宏，零引脚字面量）；页内 30+ 函数收敛为库风格子集（寄存器
 * 原语静态化，对外 init / set_channel / tx / rx / flush）；`#if
 * DYNAMIC_PACKET==0` 分支引用页外 L01_WriteSingleReg（上游残留 bug）——
 * 整枝剔除，动态包长归一为 1；页内多处 `NRF24L01_Write_Reg(FLUSH_* , 0xff)`
 * 误把 FLUSH 命令当寄存器地址（顺带多写一字节）——统一改用显式 flush
 * 命令（CS 低 + 单命令字节）。gpio_set/gpio_get = ml_gpio 位操作。 */

/* ---------- 软 SPI 原语（位操作，SPI 模式 0：上升沿采样） ---------- */

static void _cs_low(void)
{
    gpio_set(NRF24L01_PORT, NRF24L01_CSN_PIN, 0);
}

static void _cs_high(void)
{
    gpio_set(NRF24L01_PORT, NRF24L01_CSN_PIN, 1);
}

static void _ce_low(void)
{
    gpio_set(NRF24L01_PORT, NRF24L01_CE_PIN, 0);
}

static void _ce_high(void)
{
    gpio_set(NRF24L01_PORT, NRF24L01_CE_PIN, 1);
}

static uint8_t _irq_level(void)
{
    return gpio_get(NRF24L01_PORT, NRF24L01_IRQ_PIN) ? 1 : 0;
}

static uint8_t _spi_read_write_byte(uint8_t tx)
{
    uint8_t rx = 0;
    for (int8_t i = 7; i >= 0; i--) {
        gpio_set(NRF24L01_PORT, NRF24L01_CLK_PIN, 0);
        gpio_set(NRF24L01_PORT, NRF24L01_MOSI_PIN, (tx & (1u << i)) ? 1 : 0);
        gpio_set(NRF24L01_PORT, NRF24L01_CLK_PIN, 1); /* 上升沿，从机锁存 MOSI */
        if (gpio_get(NRF24L01_PORT, NRF24L01_MISO_PIN)) {
            rx |= (uint8_t)(1u << i);
        }
    }
    gpio_set(NRF24L01_PORT, NRF24L01_CLK_PIN, 0);
    return rx;
}

/* ---------- 寄存器原语（命令 = 0x00 读 / 0x20 写，寄存器地址 < 0x20） ---------- */

#define NRF_READ_REG    0x00
#define NRF_WRITE_REG   0x20
#define RD_RX_PLOAD     0x61
#define WR_TX_PLOAD     0xA0
#define FLUSH_TX        0xE1
#define FLUSH_RX        0xE2
#define R_RX_PL_WID     0x60
#define W_ACK_PLOAD     0xA8

#define CONFIG          0x00
#define EN_AA           0x01
#define EN_RXADDR       0x02
#define SETUP_AW        0x03
#define SETUP_RETR      0x04
#define RF_CH           0x05
#define RF_SETUP        0x06
#define STATUS          0x07
#define RX_ADDR_P0      0x0A
#define TX_ADDR         0x10
#define DYNPD           0x1C
#define FEATURE         0x1D /* 手册/上游拼写 FEATRUE（原文误拼），此处按惯例拼 FEATURE */

#define EN_CRC          3
#define PWR_UP          1
#define PRIM_RX         0

#define ENAA_P0         0
#define ERX_P0          0

#define AW_5BYTES       0x3
#define ARD_4000US      (0x0F << 4)
#define REPEAT_CNT      15

#define RF_DR_LOW       5
#define RF_DR_HIGH      3
#define PWR_18DB        (0x00 << 1)
#define PWR_12DB        (0x01 << 1)
#define PWR_6DB         (0x02 << 1)
#define PWR_0DB         (0x03 << 1)

#define RX_DR           6
#define TX_DS           5
#define MAX_RT          4
#define IRQ_ALL         ((1 << RX_DR) | (1 << TX_DS) | (1 << MAX_RT))

#define DPL_P0          0
#define EN_DPL          2

#define TX_TIMEOUT_MS   500u /* 发送忙等超时（原版 500ms 后重新 init 设备，改为
                              * 直接返回 NRF24L01_TX_ERR——驱动不自复位，
                              * 避免半途重配打断链路，由调用方决定重试策略） */

static uint8_t _read_reg(uint8_t addr)
{
    uint8_t value;
    _cs_low();
    _spi_read_write_byte(NRF_READ_REG | addr);
    value = _spi_read_write_byte(0xFF);
    _cs_high();
    return value;
}

static void _write_reg(uint8_t addr, uint8_t value)
{
    _cs_low();
    _spi_read_write_byte(NRF_WRITE_REG | addr);
    _spi_read_write_byte(value);
    _cs_high();
}

/* 多字节命令：cmd 可能是裸寄存器地址（TX_ADDR/RX_ADDR_P0 等，须补写位）也
 * 可能是完整命令（WR_TX_PLOAD=0xA0 等，已含 bit5——OR 幂等，两用安全）。
 * 上游写 Buf 时先 OR NRF_WRITE_REG|RegAddr（见手册 NRF24L01_Write_Buf）。 */
static void _write_buf(uint8_t cmd, const uint8_t *buf, uint8_t len)
{
    _cs_low();
    _spi_read_write_byte(NRF_WRITE_REG | cmd);
    for (uint8_t i = 0; i < len; i++) {
        _spi_read_write_byte(buf[i]);
    }
    _cs_high();
}

static void _read_buf(uint8_t cmd, uint8_t *buf, uint8_t len)
{
    _cs_low();
    _spi_read_write_byte(NRF_READ_REG | cmd);
    for (uint8_t i = 0; i < len; i++) {
        buf[i] = _spi_read_write_byte(0xFF);
    }
    _cs_high();
}

static uint8_t _clear_irq(uint8_t source)
{
    uint8_t status = _read_reg(STATUS);
    _write_reg(STATUS, status | (source & IRQ_ALL));
    return status;
}

/* ---------- 对外 API ---------- */

void nrf24l01_init(void)
{
    static const uint8_t addr[5] = {0x34, 0x43, 0x10, 0x10, 0x01};

    /* GPIO 引脚配置（CLK/MOSI/CSN/CE 推挽输出——页面 GPIO 初始化换算；
     * MISO/IRQ 上拉输入；ml_gpio 的 gpio_init 内部使能 RCC 时钟） */
    gpio_init(NRF24L01_PORT, NRF24L01_CLK_PIN, OUT_PP);
    gpio_init(NRF24L01_PORT, NRF24L01_MOSI_PIN, OUT_PP);
    gpio_init(NRF24L01_PORT, NRF24L01_CSN_PIN, OUT_PP);
    gpio_init(NRF24L01_PORT, NRF24L01_CE_PIN, OUT_PP);
    gpio_init(NRF24L01_PORT, NRF24L01_MISO_PIN, IU);
    gpio_init(NRF24L01_PORT, NRF24L01_IRQ_PIN, IU);
    _cs_high();                  /* 片选空闲高 */
    _ce_high();                  /* 上电（CE 拉高 = PWR_UP 生效前也需高电平） */
    _clear_irq(IRQ_ALL);

    /* 动态包长（DYNAMIC_PACKET 归一为 1——上游 `#if DYNAMIC_PACKET==0`
     * 分支引用页外符号 L01_WriteSingleReg，属残留 bug，整枝剔除） */
    _write_reg(DYNPD, (1 << DPL_P0));
    _write_reg(FEATURE, 0x07);  /* EN_DPL | EN_ACK_PAY | EN_DYN_ACK */

    _write_reg(CONFIG, (1 << EN_CRC) | (1 << PWR_UP));
    _write_reg(EN_AA, (1 << ENAA_P0));
    _write_reg(EN_RXADDR, (1 << ERX_P0));
    _write_reg(SETUP_AW, AW_5BYTES);
    _write_reg(SETUP_RETR, ARD_4000US | (REPEAT_CNT & 0x0F));
    _write_reg(RF_CH, 0x00);
    _write_reg(RF_SETUP, 0x26); /* 1Mbps + 0dBm 初值（后续可经 set_speed/power 改） */

    nrf24l01_set_address(addr, 5);
}

void nrf24l01_set_channel(uint8_t channel)
{
    _write_reg(RF_CH, channel & 0x7F);
}

void nrf24l01_set_speed(nrf24l01_speed_t speed)
{
    uint8_t value = _read_reg(RF_SETUP);
    value &= (uint8_t)~((1 << RF_DR_LOW) | (1 << RF_DR_HIGH));
    if (speed == NRF24L01_SPEED_250K) {
        value |= (1 << RF_DR_LOW);
    } else if (speed == NRF24L01_SPEED_2M) {
        value |= (1 << RF_DR_HIGH);
    }
    _write_reg(RF_SETUP, value);
}

void nrf24l01_set_power(nrf24l01_power_t power)
{
    uint8_t value = _read_reg(RF_SETUP) & (uint8_t)~0x07;
    switch (power) {
    case NRF24L01_POWER_M18DBM: value |= PWR_18DB; break;
    case NRF24L01_POWER_M12DBM: value |= PWR_12DB; break;
    case NRF24L01_POWER_M6DBM:  value |= PWR_6DB;  break;
    case NRF24L01_POWER_0DBM:   value |= PWR_0DB;  break;
    }
    _write_reg(RF_SETUP, value);
}

void nrf24l01_set_address(const uint8_t *addr, uint8_t len)
{
    if (len == 0 || len > 5) {
        return; /* NRF 地址宽 3-5 字节，超界直接忽略 */
    }
    _write_buf(TX_ADDR, addr, len);
    _write_buf(RX_ADDR_P0, addr, len);
}

void nrf24l01_set_mode(nrf24l01_mode_t mode)
{
    uint8_t value = _read_reg(CONFIG);
    if (mode == NRF24L01_MODE_TX) {
        value &= (uint8_t)~(1 << PRIM_RX);
    } else {
        value |= (1 << PRIM_RX);
    }
    _write_reg(CONFIG, value);
}

uint8_t nrf24l01_tx_packet(const uint8_t *buf, uint8_t len)
{
    uint8_t status;
    uint32_t timeout;

    if (len == 0 || len > NRF24L01_PAYLOAD_MAX) {
        return NRF24L01_TX_ERR;
    }

    nrf24l01_flush_tx();
    _ce_low();
    _write_buf(WR_TX_PLOAD, buf, len);
    _ce_high();                 /* CE 脉冲启动发送 */

    /* 忙等 IRQ 引脚变低（低有效 = 有发送事件）；500ms 超时返回错误 */
    timeout = 0;
    while (_irq_level() != 0) {
        delay_ms(5);
        if (++timeout >= TX_TIMEOUT_MS / 5u) {
            return NRF24L01_TX_ERR;
        }
    }

    status = _read_reg(STATUS);
    _write_reg(STATUS, status); /* 写 1 清 TX_DS / MAX_RT 标志 */

    if (status & NRF24L01_MAX_TX) {
        nrf24l01_flush_tx();
        return NRF24L01_MAX_TX;
    }
    if (status & NRF24L01_TX_OK) {
        return NRF24L01_TX_OK;
    }
    return NRF24L01_TX_ERR;
}

uint8_t nrf24l01_rx_packet(uint8_t *buf, uint8_t max_len)
{
    uint8_t status = _read_reg(STATUS);
    _write_reg(STATUS, status); /* 清中断标志 */

    if (status & NRF24L01_RX_OK) {
        uint8_t width = _read_reg(R_RX_PL_WID);
        if (width > max_len) {
            width = max_len;
        }
        if (width > 0) {
            _read_buf(RD_RX_PLOAD, buf, width);
        }
        nrf24l01_flush_rx();
        return width;
    }
    return 0;
}

void nrf24l01_flush_rx(void)
{
    _cs_low();
    _spi_read_write_byte(FLUSH_RX);
    _cs_high();
}

void nrf24l01_flush_tx(void)
{
    _cs_low();
    _spi_read_write_byte(FLUSH_TX);
    _cs_high();
}
