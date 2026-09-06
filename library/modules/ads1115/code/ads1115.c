/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《ADS1115多路模数转换器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/ads1115-multichannel-a-to-d-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ads1115.h"
#include "delay.h" /* delay_us / delay_ms：软 I2C 位操作与转换等待 */
#include "ti_msp_dl_config.h" /* ADS1115_PORT / ADS1115_SCL_PIN / ADS1115_SDA_PIN /
                               * ADS1115_SCL_IOMUX / ADS1115_SDA_IOMUX
                               * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX，
                               * 编译矩阵实测；照 AHT10_SCL_IOMUX 先例） */

/* ADS1115 软 I2C 位操作原语（立创 bsp 同款时序，照 aht10 先例：SCL 半周期
 * 2us ≈ 100kHz 级总线速度，ADS1115 规格 ≤400kHz，裕量充足；页面 `delay_us(2)/
 * 6/4/4` 混合半周期已统一为 2us）。SDA 方向切换：写 = 输出（SDA_OUT + 电平），
 * 读 = 输入（SDA_IN + 采样）。 */

#define ADS1115_SDA_OUT()                                 \
    do {                                                  \
        DL_GPIO_initDigitalOutput(ADS1115_SDA_IOMUX);     \
        DL_GPIO_setPins(ADS1115_PORT, ADS1115_SDA_PIN);   \
        DL_GPIO_enableOutput(ADS1115_PORT, ADS1115_SDA_PIN); \
    } while (0)

#define ADS1115_SDA_IN()                          \
    do {                                          \
        DL_GPIO_initDigitalInput(ADS1115_SDA_IOMUX); \
    } while (0)

#define ADS1115_SDA_GET() \
    ((DL_GPIO_readPins(ADS1115_PORT, ADS1115_SDA_PIN) & ADS1115_SDA_PIN) ? 1 : 0)

#define ADS1115_SDA(level)                                    \
    do {                                                      \
        if (level) {                                          \
            DL_GPIO_setPins(ADS1115_PORT, ADS1115_SDA_PIN);   \
        } else {                                              \
            DL_GPIO_clearPins(ADS1115_PORT, ADS1115_SDA_PIN); \
        }                                                     \
    } while (0)

#define ADS1115_SCL(level)                                    \
    do {                                                      \
        if (level) {                                          \
            DL_GPIO_setPins(ADS1115_PORT, ADS1115_SCL_PIN);   \
        } else {                                              \
            DL_GPIO_clearPins(ADS1115_PORT, ADS1115_SCL_PIN); \
        }                                                     \
    } while (0)

/* 配置缓存：s_config（MUX/PGA/DR/模式位，read_voltage 按 PGA 段换算 FSR +
 * read 按 MUX 段切换通道）、s_address（8 位写地址，默认 0x90） */
static uint16_t s_config = ADS1115_DEFAULT_CONFIG;
static uint8_t s_address = ADS1115_ADDR_DEFAULT;

/* PGA 满量程表（索引 = 配置位 bit11-9）：页面增益档（±6.144V 起）。 */
static const float s_pga_fsr[6] = {
    6.144f, 4.096f, 2.048f, 1.024f, 0.512f, 0.256f,
};

static void ads1115_iic_start(void)
{
    ADS1115_SDA_OUT();
    ADS1115_SDA(1);
    ADS1115_SCL(1);
    delay_us(2);
    ADS1115_SDA(0);
    delay_us(2);
    ADS1115_SCL(0);
}

static void ads1115_iic_stop(void)
{
    ADS1115_SDA_OUT();
    ADS1115_SCL(0);
    ADS1115_SDA(0);
    delay_us(2);
    ADS1115_SCL(1);
    ADS1115_SDA(1);
    delay_us(2);
}

/* ack 后置一位应答/非应答：is_nack = 0 应答（继续收下一字节）、1 = 非应答
 * （最后一字节，通知从机停发） */
static void ads1115_iic_send_ack(uint8_t is_nack)
{
    ADS1115_SDA_OUT();
    ADS1115_SCL(0);
    if (is_nack) {
        ADS1115_SDA(1);
    } else {
        ADS1115_SDA(0);
    }
    delay_us(2);
    ADS1115_SCL(1);
    delay_us(2);
    ADS1115_SCL(0);
    ADS1115_SDA(1);
}

static uint8_t ads1115_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    ADS1115_SDA(1);
    delay_us(1);
    ADS1115_SCL(1);
    delay_us(1);
    ADS1115_SDA_IN();
    delay_us(2);
    while ((ADS1115_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(3);
    }
    if (ack_flag <= 0) {
        ads1115_iic_stop();
        return 1; /* 超时无应答 */
    }
    ADS1115_SCL(0);
    ADS1115_SDA_OUT();
    ADS1115_SDA(0);
    return 0;
}

static void ads1115_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    ADS1115_SDA_OUT();
    ADS1115_SCL(0);
    for (i = 0; i < 8; i++) {
        ADS1115_SDA((dat & 0x80) >> 7);
        delay_us(1);
        ADS1115_SCL(1);
        delay_us(2);
        ADS1115_SCL(0);
        delay_us(2);
        dat <<= 1;
    }
}

static uint8_t ads1115_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    ADS1115_SDA_IN();
    for (i = 0; i < 8; i++) {
        ADS1115_SCL(0);
        delay_us(2);
        ADS1115_SCL(1);
        delay_us(2);
        receive <<= 1;
        if (ADS1115_SDA_GET()) {
            receive |= 1;
        }
        delay_us(1);
    }
    ADS1115_SCL(0);
    return receive;
}

uint8_t ads1115_write_register(uint8_t reg, uint8_t dat_hi, uint8_t dat_lo)
{
    ads1115_iic_start();
    ads1115_iic_send_byte(s_address); /* 器件地址 + 写 */
    if (ads1115_iic_wait_ack() != 0) {
        return 1;
    }
    ads1115_iic_send_byte(reg); /* 寄存器地址（指针） */
    if (ads1115_iic_wait_ack() != 0) {
        return 2;
    }
    ads1115_iic_send_byte(dat_hi); /* 高 8 位 */
    ads1115_iic_wait_ack();
    ads1115_iic_send_byte(dat_lo); /* 低 8 位 */
    ads1115_iic_wait_ack();
    ads1115_iic_stop();
    return 0;
}

uint8_t ads1115_write_config(uint16_t config)
{
    uint8_t rc = ads1115_write_register(
        ADS1115_REG_CONFIG, (uint8_t)(config >> 8), (uint8_t)(config & 0xFF));
    if (rc == 0) {
        s_config = config;
    }
    return rc;
}

void ads1115_init(void)
{
    (void)ads1115_write_config(s_config); /* 写默认配置 0xC283（页面 Init 同款） */
}

int16_t ads1115_read(uint8_t ch)
{
    uint16_t config;
    uint8_t dat_hi;
    uint8_t dat_lo;
    uint8_t timeout = 0;

    /* 通道选择：MUX 字段 = (0x04 | ch)（AIN0-3 单端，页面 MUX 表）；改通道后
     * 需重写配置触发新一轮转换（连续模式 MUX 切换生效） */
    config = (uint16_t)((s_config & ~ADS1115_CONFIG_MUX_MASK)
                        | (((uint16_t)(0x04u | (ch & 0x03u))) << 12));
    if (config != s_config) {
        if (ads1115_write_config(config) != 0) {
            return 0; /* 配置写失败（无应答） */
        }
    }

    /* 读转换寄存器：写指针 → 重 start + 地址+读；从机忙碌不响应时重试
     * （页面 do-while 上限 20 次 × 1ms——转换未完成/总线忙时器件不 ACK） */
    ads1115_iic_start();
    ads1115_iic_send_byte(s_address);
    if (ads1115_iic_wait_ack() != 0) {
        return 0;
    }
    ads1115_iic_send_byte(ADS1115_REG_CONVERSION);
    if (ads1115_iic_wait_ack() != 0) {
        return 0;
    }
    do {
        timeout++;
        if (timeout > 20) {
            return 0; /* 重试超时 */
        }
        delay_ms(1);
        ads1115_iic_start();
        ads1115_iic_send_byte((uint8_t)(s_address | 1)); /* 器件地址 + 读 */
    } while (ads1115_iic_wait_ack() != 0);

    dat_hi = ads1115_iic_read_byte(); /* 高 8 位 */
    ads1115_iic_send_ack(0); /* 应答（还有低字节） */
    dat_lo = ads1115_iic_read_byte(); /* 低 8 位 */
    ads1115_iic_send_ack(1); /* 非应答（最后一字节） */
    ads1115_iic_stop();

    return (int16_t)(((uint16_t)dat_hi << 8) | dat_lo);
}

float ads1115_read_voltage(uint8_t ch)
{
    int16_t raw = ads1115_read(ch);
    uint8_t pga_idx = (uint8_t)((s_config & ADS1115_CONFIG_PGA_MASK) >> 9);
    float fsr = 4.096f;

    if (pga_idx < 6u) {
        fsr = s_pga_fsr[pga_idx];
    }
    /* 补码 / 2^15 × FSR（页面分辨率式 0.000125 = 4.096/2^15 正确；页面负数
     * 分支按 0xFFFF 减位近似 + 判定未含 32768——本实现 int16_t 正确换算） */
    return (float)raw / 32768.0f * fsr;
}

uint8_t ads1115_set_gain(uint8_t pga_idx)
{
    uint16_t config;

    if (pga_idx > 5u) {
        return 1; /* 参数不合法（页面 6 档增益） */
    }
    config = (uint16_t)((s_config & ~ADS1115_CONFIG_PGA_MASK)
                        | (((uint16_t)pga_idx) << 9));
    return ads1115_write_config(config);
}

uint8_t ads1115_set_data_rate(uint8_t dr_idx)
{
    uint16_t config;

    if (dr_idx > 7u) {
        return 1; /* 参数不合法（页面 7 档数据率） */
    }
    config = (uint16_t)((s_config & ~ADS1115_CONFIG_DR_MASK)
                        | (((uint16_t)dr_idx) << 5));
    return ads1115_write_config(config);
}

void ads1115_set_address(uint8_t addr7)
{
    s_address = (uint8_t)(addr7 << 1); /* 8 位地址 = 7 位地址左移 1 + 读写位 */
}
