#include "pca9685.h"
#include "delay.h" /* delay_us / delay_ms：软 I2C 位操作与 5ms 唤醒延时 */
#include "ti_msp_dl_config.h" /* PCA9685_PORT / PCA9685_SCL_PIN / PCA9685_SDA_PIN /
                                * PCA9685_SCL_IOMUX / PCA9685_SDA_IOMUX
                                * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX，
                                * 编译矩阵实测；照 AHT10 先例） */

/* PCA9685 寄存器（数据手册；MODE1 位：7 RESTART / 5 AI 自动递增 / 4 SLEEP /
 * 0 ALLCALL） */
#define PCA9685_MODE1        0x00u
#define PCA9685_PRESCALE     0xFEu /* 频率预分频 */
#define PCA9685_LED0_ON_L    0x06u /* LEDn 寄存器基址 = 0x06 + 4×n */

#define PCA9685_CLK_HZ       25000000u /* 芯片内部振荡器（EXTCLK 25MHz） */
#define PCA9685_RESOLUTION   4096u     /* 12bit 计数（0x000-0xFFF） */

/* 软 I2C 位操作原语（照 AHT10 先例：SCL 半周期 2us ≈ 250kHz 级总线速度，
 * PCA9685 规格支持到 400kHz+；SDA 方向运行时切换） */
#define PCA9685_SDA_OUT()                                          \
    do {                                                           \
        DL_GPIO_initDigitalOutput(PCA9685_SDA_IOMUX);              \
        DL_GPIO_setPins(PCA9685_PORT, PCA9685_SDA_PIN);            \
        DL_GPIO_enableOutput(PCA9685_PORT, PCA9685_SDA_PIN);       \
    } while (0)

#define PCA9685_SDA_IN()                    \
    do {                                    \
        DL_GPIO_initDigitalInput(PCA9685_SDA_IOMUX); \
    } while (0)

#define PCA9685_SDA_GET() \
    ((DL_GPIO_readPins(PCA9685_PORT, PCA9685_SDA_PIN) & PCA9685_SDA_PIN) ? 1 : 0)

#define PCA9685_SDA(x)                                            \
    do {                                                          \
        if (x) {                                                  \
            DL_GPIO_setPins(PCA9685_PORT, PCA9685_SDA_PIN);       \
        } else {                                                  \
            DL_GPIO_clearPins(PCA9685_PORT, PCA9685_SDA_PIN);     \
        }                                                         \
    } while (0)

#define PCA9685_SCL(x)                                            \
    do {                                                          \
        if (x) {                                                  \
            DL_GPIO_setPins(PCA9685_PORT, PCA9685_SCL_PIN);       \
        } else {                                                  \
            DL_GPIO_clearPins(PCA9685_PORT, PCA9685_SCL_PIN);     \
        }                                                         \
    } while (0)

static uint8_t s_addr_write = 0x80u; /* 默认 A5..A0=0：0x40<<1 = 写地址 0x80 */
static uint16_t s_freq_hz = PCA9685_DEFAULT_FREQ_HZ;

static void pca9685_iic_start(void)
{
    PCA9685_SDA_OUT();
    PCA9685_SDA(1);
    PCA9685_SCL(1);
    delay_us(4);
    PCA9685_SDA(0);
    delay_us(4);
    PCA9685_SCL(0);
}

static void pca9685_iic_stop(void)
{
    PCA9685_SDA_OUT();
    PCA9685_SCL(0);
    PCA9685_SDA(0);
    delay_us(4);
    PCA9685_SCL(1);
    PCA9685_SDA(1);
    delay_us(4);
}

static void pca9685_iic_send_ack(uint8_t ack)
{
    PCA9685_SDA_OUT();
    PCA9685_SCL(0);
    PCA9685_SDA(0);
    delay_us(2);
    if (!ack) {
        PCA9685_SDA(0);
    } else {
        PCA9685_SDA(1);
    }
    PCA9685_SCL(1);
    delay_us(2);
    PCA9685_SCL(0);
    PCA9685_SDA(1);
}

static uint8_t pca9685_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    PCA9685_SDA(1);
    delay_us(1);
    PCA9685_SCL(1);
    delay_us(1);
    PCA9685_SDA_IN();
    delay_us(2);
    while ((PCA9685_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(3);
    }
    if (ack_flag <= 0) {
        pca9685_iic_stop();
        return 1; /* 超时无应答（器件未接/地址错） */
    }
    PCA9685_SCL(0);
    PCA9685_SDA_OUT();
    PCA9685_SDA(0);
    return 0;
}

static void pca9685_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    PCA9685_SDA_OUT();
    PCA9685_SCL(0);
    for (i = 0; i < 8; i++) {
        PCA9685_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        PCA9685_SCL(1);
        delay_us(2);
        PCA9685_SCL(0);
        delay_us(2);
        dat <<= 1;
    }
}

static uint8_t pca9685_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    PCA9685_SDA_IN();
    for (i = 0; i < 8; i++) {
        PCA9685_SCL(0);
        delay_us(2);
        PCA9685_SCL(1);
        delay_us(2);
        receive <<= 1;
        if (PCA9685_SDA_GET()) {
            receive |= 1;
        }
        delay_us(1);
    }
    PCA9685_SCL(0);
    return receive;
}

/* 写寄存器：START → 写地址 → 寄存器地址 → 数据 → STOP（逐字节等应答） */
static void pca9685_write_reg(uint8_t reg, uint8_t data)
{
    pca9685_iic_start();
    pca9685_iic_send_byte(s_addr_write);
    pca9685_iic_wait_ack();
    pca9685_iic_send_byte(reg);
    pca9685_iic_wait_ack();
    pca9685_iic_send_byte(data);
    pca9685_iic_wait_ack();
    pca9685_iic_stop();
}

/* 读寄存器：写地址 → 寄存器地址 →（重复 START）读地址 → 读一字节 + NACK */
static uint8_t pca9685_read_reg(uint8_t reg)
{
    uint8_t data;
    pca9685_iic_start();
    pca9685_iic_send_byte(s_addr_write);
    pca9685_iic_wait_ack();
    pca9685_iic_send_byte(reg);
    pca9685_iic_wait_ack();
    pca9685_iic_stop();
    delay_us(10);
    pca9685_iic_start();
    pca9685_iic_send_byte((uint8_t)(s_addr_write | 0x01u));
    pca9685_iic_wait_ack();
    data = pca9685_iic_read_byte();
    pca9685_iic_send_ack(1); /* 读一字节后非应答 */
    pca9685_iic_stop();
    return data;
}

void pca9685_set_address(uint8_t a5)
{
    if (a5 > 0x3Fu) {
        a5 = 0x3Fu; /* A5..A0 六位——0x40-0x7F 共 62 块级联 */
    }
    s_addr_write = (uint8_t)((0x40u + a5) << 1);
}

void pca9685_set_pwm(uint8_t channel, uint16_t width)
{
    uint8_t base;
    if (channel > 15) {
        return;
    }
    base = (uint8_t)(PCA9685_LED0_ON_L + 4u * channel);
    pca9685_write_reg(base, 0x00u);          /* LEDn_ON_L = 0（相位起点 0） */
    pca9685_write_reg((uint8_t)(base + 1), 0x00u); /* LEDn_ON_H = 0 */
    pca9685_write_reg((uint8_t)(base + 2), (uint8_t)(width & 0xFFu));
    pca9685_write_reg((uint8_t)(base + 3), (uint8_t)(width >> 8));
}

void pca9685_set_freq(uint16_t freq_hz)
{
    uint8_t prescale;
    uint8_t oldmode;
    uint8_t newmode;
    if (freq_hz == 0) {
        freq_hz = 1;
    }
    s_freq_hz = freq_hz;
    /* prescale = round(25000000/(4096×freq)) - 1（页面正文「119.68→120」把
     * −1 提前进除数（(50+1)）系笔误；代码公式即此式——50Hz 下
     * 25e6/204800−1 = 121.07 → 121，实际输出 50.02Hz，页面代码行为保持；
     * 浮点计算保证 round（整数先除会截断 frac，±1 差频） */
    prescale = (uint8_t)((float)PCA9685_CLK_HZ
                         / ((float)PCA9685_RESOLUTION * (float)freq_hz)
                         - 1.0f + 0.5f);
    /* 频率只能休眠时改：读回 MODE1（保护其它位）→ 置 SLEEP → 写 PRE_SCALE →
     * 写回旧值唤醒 → 等 5ms → 设自动递增/ALLCALL（页面 0xA1 行为保持） */
    oldmode = pca9685_read_reg(PCA9685_MODE1);
    newmode = (uint8_t)((oldmode & 0x7Fu) | 0x10u);
    pca9685_write_reg(PCA9685_MODE1, newmode);
    pca9685_write_reg(PCA9685_PRESCALE, prescale);
    pca9685_write_reg(PCA9685_MODE1, oldmode);
    delay_ms(5);
    pca9685_write_reg(PCA9685_MODE1, (uint8_t)(oldmode | 0xA1u));
}

void pca9685_set_angle(uint8_t channel, uint8_t angle)
{
    float min_ticks;
    float max_ticks;
    uint32_t width;
    if (angle > 180) {
        angle = 180;
    }
    /* 0.5-2.5ms 按当前频率换算 12bit 计数（与 servo 模块同口径：50Hz/20ms
     * 下 0.5ms = 4096×0.5/20 = 102.4 tick、2.5ms = 512 tick，0-180° 线性
     * 映射——浮点换算，避免整型截断把 0° 拉到 0.49ms） */
    min_ticks = PCA9685_RESOLUTION * 0.0005f * s_freq_hz;
    max_ticks = PCA9685_RESOLUTION * 0.0025f * s_freq_hz;
    width = (uint32_t)(min_ticks + (float)angle * (max_ticks - min_ticks) / 180.0f
                       + 0.5f);
    pca9685_set_pwm(channel, (uint16_t)width);
}

void pca9685_init(uint16_t freq_hz)
{
    uint8_t i;
    pca9685_write_reg(PCA9685_MODE1, 0x00u); /* 复位——页面「没有这步不工作」 */
    pca9685_set_freq(freq_hz);
    for (i = 0; i < 16; i++) {
        pca9685_set_pwm(i, 0); /* 16 路归零（ON=0/OFF=0 = 输出保持低） */
    }
}
