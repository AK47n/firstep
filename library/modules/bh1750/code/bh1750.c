#include "bh1750.h"
#include "delay.h" /* delay_us / delay_ms：软 I2C 位操作与测量等待 */
#include "ti_msp_dl_config.h" /* BH1750_PORT / BH1750_SCL_PIN / BH1750_SDA_PIN /
                               * BH1750_SCL_IOMUX / BH1750_SDA_IOMUX
                               * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX） */

/* BH1750 软 I2C 位操作原语（立创 bsp 同款时序：半周期 2us ≈ 100kHz 级，
 * BH1750 规格 ≤400kHz，裕量充足；照 aht10 先例）。
 * SDA 方向切换：写 = 输出（BH1750_SDA_OUT + 电平），读 = 输入（BH1750_SDA_IN
 * + 采样）。 */

#define BH1750_ADDR_WRITE 0x46 /* 器件地址 0x23<<1（ALT ADDRESS 接地；接电源
                                * 时地址 0xB8，改此处即可） */
#define BH1750_CMD_POWER_ON 0x01
#define BH1750_CMD_CONT_H_RES 0x10 /* 连续高分辨率：1 lx 分辨率，测量 ≥120ms */

#define BH1750_SDA_OUT()                                 \
    do {                                                 \
        DL_GPIO_initDigitalOutput(BH1750_SDA_IOMUX);     \
        DL_GPIO_setPins(BH1750_PORT, BH1750_SDA_PIN);    \
        DL_GPIO_enableOutput(BH1750_PORT, BH1750_SDA_PIN); \
    } while (0)

#define BH1750_SDA_IN()                    \
    do {                                  \
        DL_GPIO_initDigitalInput(BH1750_SDA_IOMUX); \
    } while (0)

#define BH1750_SDA_GET() \
    ((DL_GPIO_readPins(BH1750_PORT, BH1750_SDA_PIN) & BH1750_SDA_PIN) ? 1 : 0)

#define BH1750_SDA(level)                                  \
    do {                                                   \
        if (level) {                                       \
            DL_GPIO_setPins(BH1750_PORT, BH1750_SDA_PIN);  \
        } else {                                           \
            DL_GPIO_clearPins(BH1750_PORT, BH1750_SDA_PIN); \
        }                                                  \
    } while (0)

#define BH1750_SCL(level)                                  \
    do {                                                   \
        if (level) {                                       \
            DL_GPIO_setPins(BH1750_PORT, BH1750_SCL_PIN);  \
        } else {                                           \
            DL_GPIO_clearPins(BH1750_PORT, BH1750_SCL_PIN); \
        }                                                  \
    } while (0)

static void bh1750_iic_start(void)
{
    BH1750_SDA_OUT();
    BH1750_SDA(1);
    BH1750_SCL(1);
    delay_us(2);
    BH1750_SDA(0);
    delay_us(2);
    BH1750_SCL(0);
}

static void bh1750_iic_stop(void)
{
    BH1750_SDA_OUT();
    BH1750_SCL(0);
    BH1750_SDA(0);
    delay_us(2);
    BH1750_SCL(1);
    BH1750_SDA(1);
    delay_us(2);
}

/* ack 后置一位应答/非应答：is_nack = 0 应答（继续收下一字节）、1 = 非应答
 * （最后一字节，通知从机停发） */
static void bh1750_iic_send_ack(uint8_t is_nack)
{
    BH1750_SDA_OUT();
    BH1750_SCL(0);
    if (is_nack) {
        BH1750_SDA(1);
    } else {
        BH1750_SDA(0);
    }
    delay_us(2);
    BH1750_SCL(1);
    delay_us(2);
    BH1750_SCL(0);
    BH1750_SDA(1);
}

static uint8_t bh1750_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    BH1750_SDA(1);
    delay_us(1);
    BH1750_SCL(1);
    delay_us(1);
    BH1750_SDA_IN();
    delay_us(2);
    while ((BH1750_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(3);
    }
    if (ack_flag <= 0) {
        bh1750_iic_stop();
        return 1; /* 超时无应答 */
    }
    BH1750_SCL(0);
    BH1750_SDA_OUT();
    BH1750_SDA(0);
    return 0;
}

static void bh1750_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    BH1750_SDA_OUT();
    BH1750_SCL(0);
    for (i = 0; i < 8; i++) {
        BH1750_SDA((dat & 0x80) >> 7);
        delay_us(1);
        BH1750_SCL(1);
        delay_us(2);
        BH1750_SCL(0);
        delay_us(2);
        dat <<= 1;
    }
}

static uint8_t bh1750_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    BH1750_SDA_IN();
    for (i = 0; i < 8; i++) {
        BH1750_SCL(0);
        delay_us(2);
        BH1750_SCL(1);
        delay_us(2);
        receive <<= 1;
        if (BH1750_SDA_GET()) {
            receive |= 1;
        }
        delay_us(1);
    }
    BH1750_SCL(0);
    return receive;
}

/* 写一字节命令：起始 → 地址+写 → 命令 → 应答 → 停止；0=成功 1=无应答 */
static uint8_t bh1750_write_cmd(uint8_t cmd)
{
    bh1750_iic_start();
    bh1750_iic_send_byte(BH1750_ADDR_WRITE);
    if (bh1750_iic_wait_ack() != 0) {
        return 1;
    }
    bh1750_iic_send_byte(cmd);
    if (bh1750_iic_wait_ack() != 0) {
        return 1;
    }
    bh1750_iic_stop();
    return 0;
}

void bh1750_init(void)
{
    bh1750_write_cmd(BH1750_CMD_POWER_ON); /* 上电（掉电模式 → 等待测量命令） */
}

uint8_t bh1750_start_measure(void)
{
    return bh1750_write_cmd(BH1750_CMD_CONT_H_RES);
}

uint8_t bh1750_read_lux(float *lux)
{
    uint8_t dat_hi;
    uint8_t dat_lo;
    uint16_t raw;

    bh1750_iic_start();
    bh1750_iic_send_byte(BH1750_ADDR_WRITE + 1); /* 地址 + 读 */
    if (bh1750_iic_wait_ack() != 0) {
        return 1;
    }
    dat_hi = bh1750_iic_read_byte();
    bh1750_iic_send_ack(0); /* 应答 */
    dat_lo = bh1750_iic_read_byte();
    bh1750_iic_send_ack(1); /* 非应答（最后一字节） */
    bh1750_iic_stop();

    raw = ((uint16_t)dat_hi << 8) | dat_lo;
    if (lux != NULL) {
        *lux = (float)raw / 1.2f; /* 1 lx 分辨率：读数 /1.2 */
    }
    return 0;
}
