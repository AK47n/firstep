#include "tcs34725.h"
#include "delay.h" /* delay_us：软 I2C 位操作延时 */
#include "ti_msp_dl_config.h" /* TCS34725_PORT / TCS34725_SCL_PIN /
                               * TCS34725_SDA_PIN / TCS34725_SCL_IOMUX /
                               * TCS34725_SDA_IOMUX
                               * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX，
                               * 编译矩阵实测；照 AHT10_SCL_IOMUX 先例） */

/* TCS34725 软 I2C 位操作原语（立创 bsp 同款时序，照 aht10 先例：SCL 半周期
 * 2us ≈ 100kHz 级总线速度，TCS34725 规格 ≤400kHz，裕量充足；页面
 * `delay_us(1)/5/5` 混合半周期已统一为 2us）。SDA 方向切换：写 = 输出
 * （SDA_OUT + 电平），读 = 输入（SDA_IN + 采样）。 */

#define TCS34725_SDA_OUT()                                  \
    do {                                                    \
        DL_GPIO_initDigitalOutput(TCS34725_SDA_IOMUX);      \
        DL_GPIO_setPins(TCS34725_PORT, TCS34725_SDA_PIN);   \
        DL_GPIO_enableOutput(TCS34725_PORT, TCS34725_SDA_PIN); \
    } while (0)

#define TCS34725_SDA_IN()                          \
    do {                                           \
        DL_GPIO_initDigitalInput(TCS34725_SDA_IOMUX); \
    } while (0)

#define TCS34725_SDA_GET() \
    ((DL_GPIO_readPins(TCS34725_PORT, TCS34725_SDA_PIN) & TCS34725_SDA_PIN) ? 1 : 0)

#define TCS34725_SDA(level)                                    \
    do {                                                       \
        if (level) {                                           \
            DL_GPIO_setPins(TCS34725_PORT, TCS34725_SDA_PIN);  \
        } else {                                               \
            DL_GPIO_clearPins(TCS34725_PORT, TCS34725_SDA_PIN); \
        }                                                      \
    } while (0)

#define TCS34725_SCL(level)                                    \
    do {                                                       \
        if (level) {                                           \
            DL_GPIO_setPins(TCS34725_PORT, TCS34725_SCL_PIN);  \
        } else {                                               \
            DL_GPIO_clearPins(TCS34725_PORT, TCS34725_SCL_PIN); \
        }                                                      \
    } while (0)

/* max3v/min3v：页面括号法取大/小值（无分支、无中间变量，与页面宏同款） */
#define TCS34725_MAX3V(v1, v2, v3) \
    ((v1) < (v2) ? ((v2) < (v3) ? (v3) : (v2)) : ((v1) < (v3) ? (v3) : (v1)))
#define TCS34725_MIN3V(v1, v2, v3) \
    ((v1) > (v2) ? ((v2) > (v3) ? (v3) : (v2)) : ((v1) > (v3) ? (v3) : (v1)))

static void tcs34725_iic_start(void)
{
    TCS34725_SDA_OUT();
    TCS34725_SDA(1);
    TCS34725_SCL(1);
    delay_us(2);
    TCS34725_SDA(0);
    delay_us(2);
    TCS34725_SCL(0);
}

static void tcs34725_iic_stop(void)
{
    TCS34725_SDA_OUT();
    TCS34725_SCL(0);
    TCS34725_SDA(0);
    delay_us(2);
    TCS34725_SCL(1);
    TCS34725_SDA(1);
    delay_us(2);
}

/* ack 后置一位应答/非应答：is_nack = 0 应答（继续收下一字节）、1 = 非应答
 * （最后一字节，通知从机停发） */
static void tcs34725_iic_send_ack(uint8_t is_nack)
{
    TCS34725_SDA_OUT();
    TCS34725_SCL(0);
    if (is_nack) {
        TCS34725_SDA(1);
    } else {
        TCS34725_SDA(0);
    }
    delay_us(2);
    TCS34725_SCL(1);
    delay_us(2);
    TCS34725_SCL(0);
    TCS34725_SDA(1);
}

static uint8_t tcs34725_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    TCS34725_SDA(1);
    delay_us(1);
    TCS34725_SCL(1);
    delay_us(1);
    TCS34725_SDA_IN();
    delay_us(2);
    while ((TCS34725_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(3);
    }
    if (ack_flag <= 0) {
        tcs34725_iic_stop();
        return 1; /* 超时无应答 */
    }
    TCS34725_SCL(0);
    TCS34725_SDA_OUT();
    TCS34725_SDA(0);
    return 0;
}

static void tcs34725_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    TCS34725_SDA_OUT();
    TCS34725_SCL(0);
    for (i = 0; i < 8; i++) {
        TCS34725_SDA((dat & 0x80) >> 7);
        delay_us(1);
        TCS34725_SCL(1);
        delay_us(2);
        TCS34725_SCL(0);
        delay_us(2);
        dat <<= 1;
    }
}

static uint8_t tcs34725_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    TCS34725_SDA_IN();
    for (i = 0; i < 8; i++) {
        TCS34725_SCL(0);
        delay_us(2);
        TCS34725_SCL(1);
        delay_us(2);
        receive <<= 1;
        if (TCS34725_SDA_GET()) {
            receive |= 1;
        }
        delay_us(1);
    }
    TCS34725_SCL(0);
    return receive;
}

/* 底层 I2C 写：起始 → 地址+写(0x52) → data[0..n-1]（逐字节应答）→ 按 stop
 * 发送停止（页面 TCS34725_I2C_Write 同款；stop=0 供读时序的指针阶段复用） */
static void tcs34725_i2c_write(const uint8_t *data, uint8_t n, uint8_t stop)
{
    uint8_t i;
    tcs34725_iic_start();
    tcs34725_iic_send_byte(((TCS34725_ADDR << 1) & 0xFF) | 0x00); /* 地址+写 */
    tcs34725_iic_wait_ack();
    for (i = 0; i < n; i++) {
        tcs34725_iic_send_byte(data[i]);
        tcs34725_iic_wait_ack();
    }
    if (stop) {
        tcs34725_iic_stop();
    }
}

/* 底层 I2C 读：起始 → 地址+读(0x53) → 逐字节读，最后一字节非应答 → 停止
 * （页面 TCS34725_I2C_Read 同款） */
static void tcs34725_i2c_read(uint8_t *data, uint8_t n)
{
    uint8_t i;
    tcs34725_iic_start();
    tcs34725_iic_send_byte(((TCS34725_ADDR << 1) & 0xFF) | 0x01); /* 地址+读 */
    tcs34725_iic_wait_ack();
    for (i = 0; i < n; i++) {
        data[i] = tcs34725_iic_read_byte();
        tcs34725_iic_send_ack(i == n - 1 ? 1 : 0); /* 最后一字节非应答 */
    }
    tcs34725_iic_stop();
}

void tcs34725_write_reg(uint8_t sub_addr, const uint8_t *data, uint8_t n)
{
    uint8_t buf[10] = {0};
    uint8_t i;
    uint8_t total;

    buf[0] = (uint8_t)(sub_addr | TCS34725_COMMAND_BIT); /* 命令位 + 地址 */
    if (n > sizeof(buf) - 1) {
        n = (uint8_t)(sizeof(buf) - 1); /* 防御性截断（页面按寄存器写 1 字节） */
    }
    for (i = 0; i < n; i++) {
        buf[i + 1] = data[i];
    }
    total = (uint8_t)(n + 1);
    tcs34725_i2c_write(buf, total, 1);
}

void tcs34725_read_reg(uint8_t sub_addr, uint8_t *data, uint8_t n)
{
    uint8_t cmd = (uint8_t)(sub_addr | TCS34725_COMMAND_BIT);
    tcs34725_i2c_write(&cmd, 1, 0); /* 写指针（不停止） */
    tcs34725_i2c_read(data, n);
}

void tcs34725_set_integration_time(uint8_t time_val)
{
    tcs34725_write_reg(TCS34725_ATIME, &time_val, 1);
}

void tcs34725_set_gain(uint8_t gain)
{
    tcs34725_write_reg(TCS34725_CONTROL, &gain, 1);
}

void tcs34725_enable(void)
{
    uint8_t cmd = TCS34725_ENABLE_PON;
    tcs34725_write_reg(TCS34725_ENABLE, &cmd, 1); /* 页面两段写：先 PON */
    cmd = TCS34725_ENABLE_PON | TCS34725_ENABLE_AEN;
    tcs34725_write_reg(TCS34725_ENABLE, &cmd, 1); /* 再 PON|AEN */
}

void tcs34725_disable(void)
{
    uint8_t cmd = 0;
    tcs34725_read_reg(TCS34725_ENABLE, &cmd, 1);
    cmd = (uint8_t)(cmd & ~(TCS34725_ENABLE_PON | TCS34725_ENABLE_AEN));
    tcs34725_write_reg(TCS34725_ENABLE, &cmd, 1);
}

static uint16_t tcs34725_get_channel_data(uint8_t reg)
{
    uint8_t tmp[2] = {0, 0};
    tcs34725_read_reg(reg, tmp, 2);
    return (uint16_t)(((uint16_t)tmp[1] << 8) | tmp[0]); /* 低字节在前 */
}

uint8_t tcs34725_init(void)
{
    uint8_t id = 0;

    tcs34725_read_reg(TCS34725_ID, &id, 1); /* 0x44 = TCS34725，0x4D = TCS34727 */
    if (id == 0x4D || id == 0x44) { /* 页面 `== | ==` 按位或写法改 || */
        tcs34725_set_integration_time(TCS34725_INTEGRATIONTIME_24MS);
        tcs34725_set_gain(TCS34725_GAIN_1X);
        tcs34725_enable();
        return 1;
    }
    return 0;
}

uint8_t tcs34725_read_rgb(TCS34725_RGBC *out)
{
    uint8_t status = TCS34725_STATUS_AVALID;

    tcs34725_read_reg(TCS34725_STATUS, &status, 1);
    if (!(status & TCS34725_STATUS_AVALID)) {
        return 0; /* 一轮积分未完，数据未更新（调用方延后重试） */
    }
    if (out != NULL) {
        out->c = tcs34725_get_channel_data(TCS34725_CDATAL);
        out->r = tcs34725_get_channel_data(TCS34725_RDATAL);
        out->g = tcs34725_get_channel_data(TCS34725_GDATAL);
        out->b = tcs34725_get_channel_data(TCS34725_BDATAL);
    }
    return 1;
}

void tcs34725_rgb_to_hsl(const TCS34725_RGBC *rgb, TCS34725_HSL *hsl)
{
    uint8_t r;
    uint8_t g;
    uint8_t b;
    uint8_t max_val;
    uint8_t min_val;
    uint8_t dif_val;

    if (rgb == NULL || hsl == NULL || rgb->c == 0) {
        return; /* 入参非法/无 Clear 标定基准：出参不动（页面无默认值语义，
                 * 输出由调用方保证——含 c==0 时页面除法为 0 的防护） */
    }

    /* 先按 Clear 通道标定到 [0,100]（页面 RGBtoHSL 原式） */
    r = (uint8_t)(rgb->r * 100 / rgb->c);
    g = (uint8_t)(rgb->g * 100 / rgb->c);
    b = (uint8_t)(rgb->b * 100 / rgb->c);

    max_val = TCS34725_MAX3V(r, g, b);
    min_val = TCS34725_MIN3V(r, g, b);
    dif_val = (uint8_t)(max_val - min_val);

    /* 亮度 */
    hsl->l = (uint8_t)((max_val + min_val) / 2);

    if (max_val == min_val) { /* 灰度 */
        hsl->h = 0;
        hsl->s = 0;
    } else {
        /* 色调（页面原式：分段 + 补偿） */
        if (max_val == r) {
            if (g >= b) {
                hsl->h = (uint16_t)(60 * (g - b) / dif_val);
            } else {
                hsl->h = (uint16_t)(60 * (g - b) / dif_val + 360);
            }
        } else {
            if (max_val == g) {
                hsl->h = (uint16_t)(60 * (b - r) / dif_val + 120);
            } else {
                hsl->h = (uint16_t)(60 * (r - g) / dif_val + 240);
            }
        }
        /* 饱和度 */
        if (hsl->l <= 50) {
            hsl->s = (uint8_t)(dif_val * 100 / (max_val + min_val));
        } else {
            hsl->s = (uint8_t)(dif_val * 100 / (200 - (max_val + min_val)));
        }
    }
}
