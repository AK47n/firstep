#include "sht20.h"
#include "delay.h" /* delay_us / delay_ms：软 I2C 位操作与读应答重试 */
#include "ti_msp_dl_config.h" /* SHT20_PORT / SHT20_SCL_PIN / SHT20_SDA_PIN /
                                * SHT20_SCL_IOMUX / SHT20_SDA_IOMUX
                                * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX，
                                * 照 AHT10/SHT30 先例） */

/* SHT20 软 I2C 位操作原语（立创 bsp 同款时序归一为 sht30 同款：SCL 半周期
 * 5us ≈ 100kHz 级总线速度，SHT2x 规格 ≤400kHz，裕量充足）。
 * SDA 方向切换：写 = 输出（SDA_OUT + 电平），读 = 输入（SDA_IN + 采样）。 */

#define SHT20_SDA_OUT()                                        \
    do {                                                       \
        DL_GPIO_initDigitalOutput(SHT20_SDA_IOMUX);            \
        DL_GPIO_setPins(SHT20_PORT, SHT20_SDA_PIN);            \
        DL_GPIO_enableOutput(SHT20_PORT, SHT20_SDA_PIN);       \
    } while (0)

#define SHT20_SDA_IN()                    \
    do {                                  \
        DL_GPIO_initDigitalInput(SHT20_SDA_IOMUX); \
    } while (0)

#define SHT20_SDA_GET() \
    ((DL_GPIO_readPins(SHT20_PORT, SHT20_SDA_PIN) & SHT20_SDA_PIN) ? 1 : 0)

#define SHT20_SDA(x)                                              \
    do {                                                          \
        if (x) {                                                  \
            DL_GPIO_setPins(SHT20_PORT, SHT20_SDA_PIN);           \
        } else {                                                  \
            DL_GPIO_clearPins(SHT20_PORT, SHT20_SDA_PIN);         \
        }                                                         \
    } while (0)

#define SHT20_SCL(x)                                              \
    do {                                                          \
        if (x) {                                                  \
            DL_GPIO_setPins(SHT20_PORT, SHT20_SCL_PIN);           \
        } else {                                                  \
            DL_GPIO_clearPins(SHT20_PORT, SHT20_SCL_PIN);         \
        }                                                         \
    } while (0)

static void sht20_iic_start(void)
{
    SHT20_SDA_OUT();
    SHT20_SCL(0);
    SHT20_SDA(1);
    SHT20_SCL(1);
    delay_us(5);
    SHT20_SDA(0);
    delay_us(5);
    SHT20_SCL(0);
    delay_us(5);
}

static void sht20_iic_stop(void)
{
    SHT20_SDA_OUT();
    SHT20_SCL(0);
    SHT20_SDA(0);
    SHT20_SCL(1);
    delay_us(5);
    SHT20_SDA(1);
    delay_us(5);
}

static void sht20_iic_send_ack(uint8_t ack)
{
    SHT20_SDA_OUT();
    SHT20_SCL(0);
    SHT20_SDA(0); /* 页面原式：先置 0，再按 ack 重设（ack=0 时同值二次写） */
    delay_us(5);
    if (!ack) {
        SHT20_SDA(0);
    } else {
        SHT20_SDA(1);
    }
    SHT20_SCL(1);
    delay_us(5);
    SHT20_SCL(0);
    SHT20_SDA(1);
}

static uint8_t sht20_iic_wait_ack(void)
{
    uint8_t ack_flag = 10; /* 页面超时计数（10×5us） */
    SHT20_SCL(0);
    SHT20_SDA(1);
    SHT20_SDA_IN();
    SHT20_SCL(1);
    while ((SHT20_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        sht20_iic_stop();
        return 1; /* 超时无应答 */
    }
    SHT20_SCL(0);
    SHT20_SDA_OUT();
    return 0;
}

static void sht20_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    SHT20_SDA_OUT();
    SHT20_SCL(0);
    for (i = 0; i < 8; i++) {
        SHT20_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        SHT20_SCL(1);
        delay_us(5);
        SHT20_SCL(0);
        delay_us(5);
        dat <<= 1;
    }
}

static uint8_t sht20_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    SHT20_SDA_IN();
    for (i = 0; i < 8; i++) {
        SHT20_SCL(0);
        delay_us(5);
        SHT20_SCL(1);
        delay_us(5);
        receive <<= 1;
        if (SHT20_SDA_GET()) {
            receive |= 1;
        }
        delay_us(5);
    }
    SHT20_SCL(0);
    return receive;
}

/* 单段测量（页面 SHT20_Read 单值形态）：写地址 → 写测量命令 → 轮询读地址
 * 应答直到测量完成（no-hold 单次——页面 do-while 裸循环改 ≤50×2ms 重试，
 * 覆盖页面 85ms/29ms 最长测量）→ 读 2 字节 + NACK + 停止；
 * 返回 0 = 成功（raw 出参为 16bit 原始值）、1 = 写地址应答失败、
 * 2 = 测量命令应答失败、3 = 读地址应答超时。 */
static uint8_t sht20_measure_once(uint8_t cmd, uint16_t *raw)
{
    uint8_t data_h = 0;
    uint8_t data_l = 0;
    uint16_t retry = 0;

    sht20_iic_start();
    sht20_iic_send_byte((uint8_t)((SHT20_ADDR << 1) | 0u)); /* 写地址 */
    if (sht20_iic_wait_ack() == 1) {
        return 1;
    }
    sht20_iic_send_byte(cmd); /* 测量命令（0xF3 温度 / 0xF5 湿度） */
    if (sht20_iic_wait_ack() == 1) {
        return 2;
    }

    /* 等待测量完成：重发读地址直到有应答（no-hold 模式传感器完成前 NACK） */
    do {
        if (retry >= SHT20_READ_RETRY_MAX) {
            return 3;
        }
        retry++;
        delay_ms(SHT20_READ_RETRY_MS);
        sht20_iic_start();
        sht20_iic_send_byte((uint8_t)((SHT20_ADDR << 1) | 1u)); /* 读地址 */
    } while (sht20_iic_wait_ack() == 1);

    delay_us(20); /* 页面读前稳定拍（原值保留） */

    data_h = sht20_iic_read_byte();
    sht20_iic_send_ack(0);
    data_l = sht20_iic_read_byte();
    sht20_iic_send_ack(1); /* 无 CRC 按页面：末字节非应答 + 停止 */
    sht20_iic_stop();

    /* 14bit 数据左对齐、低 2 位为状态位——物理计算前置 0（页面正文要求、
     * 页面代码未实现——按 SHT2x 手册修正 & 0xFFFC） */
    *raw = (uint16_t)((((uint16_t)data_h << 8) | data_l) & 0xFFFCu);
    return 0;
}

void sht20_init(void)
{
    /* 单次测量模式无器件初始化序列（页面 bsp 无 init 函数）——
     * 引脚配置由 SYSCFG_DL_init() 完成，空实现占位。 */
}

uint8_t sht20_read(float *temperature_c, float *humidity_rh)
{
    uint16_t raw = 0;
    uint16_t ret_t = 0;
    uint16_t ret_h = 0;

    /* 温度段（0xF3）——页面公式原式：raw/65536×175.72−46.85 */
    if (sht20_measure_once(SHT20_CMD_TEMP, &raw) != 0) {
        return 1;
    }
    ret_t = raw;
    /* 湿度段（0xF5）——页面公式原式：raw/65536×125−6 */
    if (sht20_measure_once(SHT20_CMD_HUMI, &raw) != 0) {
        return 2;
    }
    ret_h = raw;

    if (temperature_c != NULL) {
        *temperature_c = (float)ret_t / 65536.0f * 175.72f - 46.85f;
    }
    if (humidity_rh != NULL) {
        *humidity_rh = (float)ret_h / 65536.0f * 125.0f - 6.0f;
    }
    return 0;
}
