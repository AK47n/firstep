#include "ags10.h"
#include "delay.h" /* delay_us / delay_ms：软 I2C 位操作与读应答重试 */
#include "ti_msp_dl_config.h" /* AGS10_SCL_PORT/PIN、AGS10_SDA_PORT/PIN、
                                * AGS10_SCL_IOMUX / AGS10_SDA_IOMUX
                                * （SysConfig 生成命名：<实例>_<引脚名>_PORT/
                                * PIN/_IOMUX——SCL/SDA 跨 GPIOB/GPIOA 两端口，
                                * 生成器按引脚名分派各口宏，无组合 AGS10_PORT；
                                * 编译矩阵实测，照 max7219 先例） */

/* AGS10 软 I2C 位操作原语（立创 bsp 同款时序：半周期 5us ≈ 100kHz 级。
 * 页面规格表注明 I2C 接口速率 ≤15kHz 与页面代码时序不一致——按页面代码
 * 实现，真机通信异常时按规格调慢 SCL 半周期延时即可（唯一时序宏点）。
 * SDA 方向切换：写 = 输出（SDA_OUT + 电平），读 = 输入（SDA_IN + 采样）。 */

#define AGS10_SDA_OUT()                                        \
    do {                                                       \
        DL_GPIO_initDigitalOutput(AGS10_SDA_IOMUX);            \
        DL_GPIO_setPins(AGS10_SDA_PORT, AGS10_SDA_PIN);        \
        DL_GPIO_enableOutput(AGS10_SDA_PORT, AGS10_SDA_PIN);   \
    } while (0)

#define AGS10_SDA_IN()                          \
    do {                                        \
        DL_GPIO_initDigitalInput(AGS10_SDA_IOMUX); \
    } while (0)

#define AGS10_SDA_GET() \
    ((DL_GPIO_readPins(AGS10_SDA_PORT, AGS10_SDA_PIN) & AGS10_SDA_PIN) ? 1 : 0)

#define AGS10_SDA(x)                                                 \
    do {                                                             \
        if (x) {                                                     \
            DL_GPIO_setPins(AGS10_SDA_PORT, AGS10_SDA_PIN);          \
        } else {                                                     \
            DL_GPIO_clearPins(AGS10_SDA_PORT, AGS10_SDA_PIN);        \
        }                                                            \
    } while (0)

#define AGS10_SCL(x)                                                 \
    do {                                                             \
        if (x) {                                                     \
            DL_GPIO_setPins(AGS10_SCL_PORT, AGS10_SCL_PIN);          \
        } else {                                                     \
            DL_GPIO_clearPins(AGS10_SCL_PORT, AGS10_SCL_PIN);        \
        }                                                            \
    } while (0)

static void ags10_iic_start(void)
{
    AGS10_SDA_OUT();
    AGS10_SDA(1);
    AGS10_SCL(1);
    delay_us(5);
    AGS10_SDA(0);
    delay_us(5);
    AGS10_SCL(0);
    delay_us(5);
}

static void ags10_iic_stop(void)
{
    AGS10_SDA_OUT();
    AGS10_SCL(0);
    AGS10_SDA(0);
    AGS10_SCL(1);
    delay_us(5);
    AGS10_SDA(1);
    delay_us(5);
}

static void ags10_iic_send_nack(void)
{
    AGS10_SDA_OUT();
    AGS10_SCL(0);
    AGS10_SDA(0);
    AGS10_SDA(1);
    AGS10_SCL(1);
    delay_us(5);
    AGS10_SCL(0);
    AGS10_SDA(0);
}

static void ags10_iic_send_ack(void)
{
    AGS10_SDA_OUT();
    AGS10_SCL(0);
    AGS10_SDA(1);
    AGS10_SDA(0);
    AGS10_SCL(1);
    delay_us(5);
    AGS10_SCL(0);
    AGS10_SDA(1);
}

static uint8_t ags10_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    AGS10_SCL(0);
    AGS10_SDA(1);
    AGS10_SDA_IN();
    delay_us(5);
    AGS10_SCL(1);
    delay_us(5);
    while ((AGS10_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        ags10_iic_stop();
        return 1; /* 非应答/超时（页面 1=非应答 0=应答） */
    }
    AGS10_SCL(0);
    AGS10_SDA_OUT();
    return 0;
}

static void ags10_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    AGS10_SDA_OUT();
    AGS10_SCL(0);
    for (i = 0; i < 8; i++) {
        AGS10_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        AGS10_SCL(1);
        delay_us(5);
        AGS10_SCL(0);
        delay_us(5);
        dat <<= 1;
    }
}

static uint8_t ags10_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    AGS10_SDA_IN();
    for (i = 0; i < 8; i++) {
        AGS10_SCL(0);
        delay_us(5);
        AGS10_SCL(1);
        delay_us(5);
        receive <<= 1;
        if (AGS10_SDA_GET()) {
            receive |= 1;
        }
    }
    AGS10_SCL(0);
    return receive;
}

/* CRC8（页面 Calc_CRC8 原式，自包含）：初值 0xFF、多项式 0x31
 * （x8 + x5 + x4 +1）——每个数据字节逐位
 * (crc & 0x80) ? (crc<<1)^POLYNOMIAL : (crc<<1)。 */
static uint8_t ags10_crc8(const uint8_t *dat, uint8_t num)
{
    uint8_t i;
    uint8_t byte;
    uint8_t crc = 0xFFu;

    for (byte = 0; byte < num; byte++) {
        crc ^= dat[byte];
        for (i = 0; i < 8; i++) {
            if (crc & 0x80u) {
                crc = (uint8_t)((crc << 1) ^ 0x31u);
            } else {
                crc = (uint8_t)(crc << 1);
            }
        }
    }
    return crc;
}

void ags10_init(void)
{
    /* AGS10 无独立初始化序列（页面演示上电直接读；模块预热 ≥120s 期间
     * 读数起步属器件特性，等待归调用方——mlx90614/at24c02 空实现先例） */
}

uint8_t ags10_read(uint32_t *voc_ppb)
{
    uint8_t timeout = 0;
    uint8_t data[5] = {0};

    /* 写寄存器 0x00（页面原式：地址 0x34 + 寄存器值——错误码 1/2 页面语义） */
    ags10_iic_start();
    ags10_iic_send_byte((uint8_t)((AGS10_ADDR << 1) | 0u)); /* 写 0x34 */
    if (ags10_iic_wait_ack() == 1) {
        return 1; /* 通信失败 */
    }
    ags10_iic_send_byte(AGS10_REG_TVOC);
    if (ags10_iic_wait_ack() == 1) {
        return 2; /* 发送失败 */
    }
    ags10_iic_stop();

    /* 读地址应答重试（页面函数注释：≤50×1ms；页面实现比较方向写反——
     * 循环一次即退、超时分支永不触发——本实现按注释语义修正为 timeout
     * < AGS10_RETRY_MAX，上游缺陷记录，ir_remote/nrf24l01 先例） */
    do {
        delay_ms(1);
        timeout++;
        ags10_iic_start();
        ags10_iic_send_byte((uint8_t)((AGS10_ADDR << 1) | 1u)); /* 读 0x35 */
    } while ((ags10_iic_wait_ack() == 1) && (timeout < AGS10_RETRY_MAX));
    if (timeout >= AGS10_RETRY_MAX) {
        return 3; /* 等待超时 */
    }

    /* 5 字节回包：状态 + TVOC 24bit（data[1..3]）+ CRC（data[4]，最后一字节
     * 非应答——页面原式） */
    data[0] = ags10_iic_read_byte();
    ags10_iic_send_ack();
    data[1] = ags10_iic_read_byte();
    ags10_iic_send_ack();
    data[2] = ags10_iic_read_byte();
    ags10_iic_send_ack();
    data[3] = ags10_iic_read_byte();
    ags10_iic_send_ack();
    data[4] = ags10_iic_read_byte();
    ags10_iic_send_nack();
    ags10_iic_stop();

    if (ags10_crc8(data, 4) != data[4]) {
        return 4; /* 校验失败（页面失败码 4） */
    }
    if (voc_ppb != NULL) {
        *voc_ppb = ((uint32_t)data[1] << 16) | ((uint32_t)data[2] << 8) | data[3];
    }
    return 0;
}
