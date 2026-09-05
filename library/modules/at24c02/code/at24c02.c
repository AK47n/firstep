#include "at24c02.h"
#include "delay.h" /* delay_ms：软 I2C 位操作延时与写周期等待 */
#include "ti_msp_dl_config.h" /* AT24C02_PORT / AT24C02_SCL_PIN / AT24C02_SDA_PIN /
                               * AT24C02_SCL_IOMUX / AT24C02_SDA_IOMUX
                               * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX，
                               * 编译矩阵实测；照 AHT10_SCL_IOMUX 先例） */

/* AT24C02 软 I2C 位操作原语（立创 bsp 同款时序，照 aht10 先例：SCL 半周期
 * 2us ≈ 100kHz 级总线速度，AT24C02 400kHz 规格裕量充足；页面 `delay_us(1)/5/5`
 * 混合半周期已统一为 2us）。SDA 方向切换：写 = 输出（SDA_OUT + 电平），
 * 读 = 输入（SDA_IN + 采样）。 */

#define AT24C02_SDA_OUT()                                 \
    do {                                                  \
        DL_GPIO_initDigitalOutput(AT24C02_SDA_IOMUX);     \
        DL_GPIO_setPins(AT24C02_PORT, AT24C02_SDA_PIN);   \
        DL_GPIO_enableOutput(AT24C02_PORT, AT24C02_SDA_PIN); \
    } while (0)

#define AT24C02_SDA_IN()                          \
    do {                                          \
        DL_GPIO_initDigitalInput(AT24C02_SDA_IOMUX); \
    } while (0)

#define AT24C02_SDA_GET() \
    ((DL_GPIO_readPins(AT24C02_PORT, AT24C02_SDA_PIN) & AT24C02_SDA_PIN) ? 1 : 0)

#define AT24C02_SDA(level)                                    \
    do {                                                      \
        if (level) {                                          \
            DL_GPIO_setPins(AT24C02_PORT, AT24C02_SDA_PIN);   \
        } else {                                              \
            DL_GPIO_clearPins(AT24C02_PORT, AT24C02_SDA_PIN); \
        }                                                     \
    } while (0)

#define AT24C02_SCL(level)                                    \
    do {                                                      \
        if (level) {                                          \
            DL_GPIO_setPins(AT24C02_PORT, AT24C02_SCL_PIN);   \
        } else {                                              \
            DL_GPIO_clearPins(AT24C02_PORT, AT24C02_SCL_PIN); \
        }                                                     \
    } while (0)

static void at24c02_iic_start(void)
{
    AT24C02_SDA_OUT();
    AT24C02_SDA(1);
    AT24C02_SCL(1);
    delay_us(2);
    AT24C02_SDA(0);
    delay_us(2);
    AT24C02_SCL(0);
}

static void at24c02_iic_stop(void)
{
    AT24C02_SDA_OUT();
    AT24C02_SCL(0);
    AT24C02_SDA(0);
    delay_us(2);
    AT24C02_SCL(1);
    AT24C02_SDA(1);
    delay_us(2);
}

/* ack 后置一位应答/非应答：is_nack = 0 应答（继续收下一字节）、1 = 非应答
 * （最后一字节，通知从机停发） */
static void at24c02_iic_send_ack(uint8_t is_nack)
{
    AT24C02_SDA_OUT();
    AT24C02_SCL(0);
    if (is_nack) {
        AT24C02_SDA(1);
    } else {
        AT24C02_SDA(0);
    }
    delay_us(2);
    AT24C02_SCL(1);
    delay_us(2);
    AT24C02_SCL(0);
    AT24C02_SDA(1);
}

static uint8_t at24c02_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    AT24C02_SDA(1);
    delay_us(1);
    AT24C02_SCL(1);
    delay_us(1);
    AT24C02_SDA_IN();
    delay_us(2);
    while ((AT24C02_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(3);
    }
    if (ack_flag <= 0) {
        at24c02_iic_stop();
        return 1; /* 超时无应答 */
    }
    AT24C02_SCL(0);
    AT24C02_SDA_OUT();
    AT24C02_SDA(0);
    return 0;
}

static void at24c02_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    AT24C02_SDA_OUT();
    AT24C02_SCL(0);
    for (i = 0; i < 8; i++) {
        AT24C02_SDA((dat & 0x80) >> 7);
        delay_us(1);
        AT24C02_SCL(1);
        delay_us(2);
        AT24C02_SCL(0);
        delay_us(2);
        dat <<= 1;
    }
}

static uint8_t at24c02_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    AT24C02_SDA_IN();
    for (i = 0; i < 8; i++) {
        AT24C02_SCL(0);
        delay_us(2);
        AT24C02_SCL(1);
        delay_us(2);
        receive <<= 1;
        if (AT24C02_SDA_GET()) {
            receive |= 1;
        }
        delay_us(1);
    }
    AT24C02_SCL(0);
    return receive;
}

void at24c02_init(void)
{
    /* I2C 存储器无初始化序列（即插即用，页面演示无 init），空实现占位保持
     * 模块 API 一致；在线校验由读写判（无应答 = 未接/写周期中）。 */
}

void at24c02_write_byte(uint8_t addr, uint8_t data)
{
    at24c02_iic_start();
    at24c02_iic_send_byte(AT24C02_ADDR_WRITE); /* 器件地址 + 写（0xA0） */
    at24c02_iic_wait_ack();
    at24c02_iic_send_byte(addr); /* 字节地址 */
    at24c02_iic_wait_ack();
    at24c02_iic_send_byte(data);
    at24c02_iic_wait_ack();
    at24c02_iic_stop(); /* 停止后进入内部写周期（~5ms 不响应） */
}

uint8_t at24c02_read_byte(uint8_t addr)
{
    uint8_t data;

    at24c02_iic_start();
    at24c02_iic_send_byte(AT24C02_ADDR_WRITE); /* 伪写定位 */
    at24c02_iic_wait_ack();
    at24c02_iic_send_byte(addr);
    at24c02_iic_wait_ack();
    at24c02_iic_start();
    at24c02_iic_send_byte(AT24C02_ADDR_READ); /* 器件地址 + 读（0xA1） */
    at24c02_iic_wait_ack();
    data = at24c02_iic_read_byte();
    at24c02_iic_send_ack(1); /* 非应答（最后一字节） */
    at24c02_iic_stop();
    return data;
}

void at24c02_wait_write_done(void)
{
    delay_ms(AT24C02_WRITE_CYCLE_MS); /* 页面演示写后 delay_ms(5) 再读 */
}

uint8_t at24c02_write_page(uint8_t addr, const uint8_t *data, uint8_t len)
{
    uint8_t i;

    /* 页边界校验：整页写入不跨页（页面「超过 P+1 字节地址计数器自动翻转、
     * 先前写入的数据被覆盖」）——16 字节页缓冲且同页才安全 */
    if (data == NULL || len == 0 || len > AT24C02_PAGE_SIZE
        || (addr % AT24C02_PAGE_SIZE) + len > AT24C02_PAGE_SIZE) {
        return 1;
    }
    at24c02_iic_start();
    at24c02_iic_send_byte(AT24C02_ADDR_WRITE);
    if (at24c02_iic_wait_ack() != 0) {
        return 2;
    }
    at24c02_iic_send_byte(addr);
    if (at24c02_iic_wait_ack() != 0) {
        return 2;
    }
    for (i = 0; i < len; i++) {
        at24c02_iic_send_byte(data[i]);
        if (at24c02_iic_wait_ack() != 0) {
            return 2;
        }
    }
    at24c02_iic_stop(); /* 停止后单写周期烧写整页 */
    return 0;
}

uint8_t at24c02_read_block(uint8_t addr, uint8_t *buf, uint8_t len)
{
    uint8_t i;

    if (buf == NULL || len == 0) {
        return 1;
    }
    at24c02_iic_start();
    at24c02_iic_send_byte(AT24C02_ADDR_WRITE); /* 伪写定位 */
    if (at24c02_iic_wait_ack() != 0) {
        return 2;
    }
    at24c02_iic_send_byte(addr);
    if (at24c02_iic_wait_ack() != 0) {
        return 2;
    }
    at24c02_iic_start();
    at24c02_iic_send_byte(AT24C02_ADDR_READ);
    if (at24c02_iic_wait_ack() != 0) {
        return 2;
    }
    for (i = 0; i < len; i++) {
        buf[i] = at24c02_iic_read_byte();
        at24c02_iic_send_ack(i == len - 1 ? 1 : 0); /* 最后一字节 NACK */
    }
    at24c02_iic_stop();
    return 0;
}
