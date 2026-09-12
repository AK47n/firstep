/* 来源：Honeywell HMC5883L 三轴数字磁力计数据手册（Datasheet 900405 Rev E）
 * + 库内与桌面工作目录遗留的旧实现 ml_hmc5883l（多份副本逐字节相同；
 * 本文件是对其**重写**，缺陷清单见下方头文件注释与 manifest
 * notes）。
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、引脚宏参数化、
 * I2C 原语族静态化、ADR 0009 纯驱动无状态机）。 */

#include "hmc5883l.h"
#include "delay.h" /* delay_us：软 I2C 位操作半周期 */
#include "ti_msp_dl_config.h" /* HMC5883L_PORT / HMC5883L_SCL_PIN / HMC5883L_SDA_PIN /
                               * HMC5883L_SCL_IOMUX / HMC5883L_SDA_IOMUX
                               * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX） */

/* 软 I2C 位操作原语（照 aht10/bh1750 先例：半周期 2us ≈ 100kHz 级；
 * HMC5883L 支持 100kHz 标准模式与 400kHz 快速模式，裕量充足）。
 * SDA 方向运行时切换：写 = 输出，读 = 输入采样。 */

#define HMC5883L_SDA_OUT()                                   \
    do {                                                     \
        DL_GPIO_initDigitalOutput(HMC5883L_SDA_IOMUX);       \
        DL_GPIO_setPins(HMC5883L_PORT, HMC5883L_SDA_PIN);    \
        DL_GPIO_enableOutput(HMC5883L_PORT, HMC5883L_SDA_PIN); \
    } while (0)

#define HMC5883L_SDA_IN()                            \
    do {                                             \
        DL_GPIO_initDigitalInput(HMC5883L_SDA_IOMUX); \
    } while (0)

#define HMC5883L_SDA_GET() \
    ((DL_GPIO_readPins(HMC5883L_PORT, HMC5883L_SDA_PIN) & HMC5883L_SDA_PIN) ? 1 : 0)

#define HMC5883L_SDA(level)                                     \
    do {                                                        \
        if (level) {                                            \
            DL_GPIO_setPins(HMC5883L_PORT, HMC5883L_SDA_PIN);   \
        } else {                                                \
            DL_GPIO_clearPins(HMC5883L_PORT, HMC5883L_SDA_PIN); \
        }                                                       \
    } while (0)

#define HMC5883L_SCL(level)                                     \
    do {                                                        \
        if (level) {                                            \
            DL_GPIO_setPins(HMC5883L_PORT, HMC5883L_SCL_PIN);   \
        } else {                                                \
            DL_GPIO_clearPins(HMC5883L_PORT, HMC5883L_SCL_PIN); \
        }                                                       \
    } while (0)

static void hmc5883l_iic_start(void)
{
    HMC5883L_SDA_OUT();
    HMC5883L_SDA(1);
    HMC5883L_SCL(1);
    delay_us(2);
    HMC5883L_SDA(0);
    delay_us(2);
    HMC5883L_SCL(0);
}

static void hmc5883l_iic_stop(void)
{
    HMC5883L_SDA_OUT();
    HMC5883L_SCL(0);
    HMC5883L_SDA(0);
    delay_us(2);
    HMC5883L_SCL(1);
    HMC5883L_SDA(1);
    delay_us(2);
}

/* is_nack = 0 应答（继续收）、1 = 非应答（最后一字节，通知从机停发） */
static void hmc5883l_iic_send_ack(uint8_t is_nack)
{
    HMC5883L_SDA_OUT();
    HMC5883L_SCL(0);
    if (is_nack) {
        HMC5883L_SDA(1);
    } else {
        HMC5883L_SDA(0);
    }
    delay_us(2);
    HMC5883L_SCL(1);
    delay_us(2);
    HMC5883L_SCL(0);
    HMC5883L_SDA(1);
}

static uint8_t hmc5883l_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    HMC5883L_SDA(1);
    delay_us(1);
    HMC5883L_SCL(1);
    delay_us(1);
    HMC5883L_SDA_IN();
    delay_us(2);
    while ((HMC5883L_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(3);
    }
    if (ack_flag <= 0) {
        hmc5883l_iic_stop();
        return 1; /* 超时无应答 */
    }
    HMC5883L_SCL(0);
    HMC5883L_SDA_OUT();
    HMC5883L_SDA(0);
    return 0;
}

static void hmc5883l_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    HMC5883L_SDA_OUT();
    HMC5883L_SCL(0);
    for (i = 0; i < 8; i++) {
        HMC5883L_SDA((dat & 0x80) >> 7);
        delay_us(1);
        HMC5883L_SCL(1);
        delay_us(2);
        HMC5883L_SCL(0);
        delay_us(2);
        dat <<= 1;
    }
}

static uint8_t hmc5883l_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    HMC5883L_SDA_IN();
    for (i = 0; i < 8; i++) {
        HMC5883L_SCL(0);
        delay_us(2);
        HMC5883L_SCL(1);
        delay_us(2);
        receive <<= 1;
        if (HMC5883L_SDA_GET()) {
            receive |= 1;
        }
        delay_us(1);
    }
    HMC5883L_SCL(0);
    return receive;
}

/* 写寄存器：起始 → 写地址 → 寄存器号 → 数据 → 应答 → 停止；0=成功 1=无应答 */
static uint8_t hmc5883l_write_reg(uint8_t reg, uint8_t value)
{
    hmc5883l_iic_start();
    hmc5883l_iic_send_byte(HMC5883L_ADDR_WRITE);
    if (hmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    hmc5883l_iic_send_byte(reg);
    if (hmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    hmc5883l_iic_send_byte(value);
    if (hmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    hmc5883l_iic_stop();
    return 0;
}

/* 连续读：起始 → 写地址（定寄存器）→ 起始 → 读地址 → 逐字节读（前 n-1 应答、
 * 末字节非应答）→ 停止；0=成功 1=无应答（两处读地址都不放过——旧实现把读
 * 地址 OR 0x01 当寄存器用，见头文件缺陷清单①） */
static uint8_t hmc5883l_read_regs(uint8_t reg, uint8_t *buf, uint8_t len)
{
    uint8_t i;

    hmc5883l_iic_start();
    hmc5883l_iic_send_byte(HMC5883L_ADDR_WRITE);
    if (hmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    hmc5883l_iic_send_byte(reg);
    if (hmc5883l_iic_wait_ack() != 0) {
        return 1;
    }

    hmc5883l_iic_start();
    hmc5883l_iic_send_byte(HMC5883L_ADDR_READ);
    if (hmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    for (i = 0; i < len; i++) {
        buf[i] = hmc5883l_iic_read_byte();
        hmc5883l_iic_send_ack((i + 1 == len) ? 1 : 0);
    }
    hmc5883l_iic_stop();
    return 0;
}

/* 两字节大端拼 16 位有符号（缺陷清单③：旧实现 data_l | (data_h << 8) 无符号
 * 扩展，负磁场读成 32768+ 的大正数） */
static int16_t hmc5883l_join_s16(uint8_t hi, uint8_t lo)
{
    return (int16_t)(((uint16_t)hi << 8) | (uint16_t)lo);
}

uint8_t hmc5883l_init(void)
{
    uint8_t id[3];

    /* 器件 ID（0x0A..0x0C）= 'H','4','3'：读不到 = 总线不通（1）、读得到但
     * 不是这三个字节 = 型号不符（2——市售「HMC5883L 模块」多为 QMC5883L，
     * 两者寄存器语义完全不同，必须先分辨再初始化，见头文件缺陷清单⑥） */
    if (hmc5883l_read_regs(HMC5883L_REG_ID_A, id, 3) != 0) {
        return 1;
    }
    if (id[0] != HMC5883L_ID_A_VALUE || id[1] != HMC5883L_ID_B_VALUE
        || id[2] != HMC5883L_ID_C_VALUE) {
        return 2;
    }

    if (hmc5883l_write_reg(HMC5883L_REG_CRA, HMC5883L_CRA_8AVG_15HZ_NORMAL) != 0) {
        return 1;
    }
    if (hmc5883l_write_reg(HMC5883L_REG_CRB, HMC5883L_CRB_GAIN_1_3GA) != 0) {
        return 1;
    }
    if (hmc5883l_write_reg(HMC5883L_REG_MR, HMC5883L_MR_CONTINUOUS) != 0) {
        return 1;
    }
    return 0;
}

uint8_t hmc5883l_read(int16_t *x, int16_t *y, int16_t *z)
{
    uint8_t buf[HMC5883L_DATA_LEN];

    if (hmc5883l_read_regs(HMC5883L_REG_DATA_X_MSB, buf, HMC5883L_DATA_LEN) != 0) {
        return 1;
    }
    /* 器件数据区顺序 = X(0x03/04)、Z(0x05/06)、Y(0x07/08)——不是 X-Y-Z
     * （缺陷清单②：旧实现宏名按 X-Y-Z 命名，极易错位） */
    if (x != NULL) {
        *x = hmc5883l_join_s16(buf[0], buf[1]);
    }
    if (z != NULL) {
        *z = hmc5883l_join_s16(buf[2], buf[3]);
    }
    if (y != NULL) {
        *y = hmc5883l_join_s16(buf[4], buf[5]);
    }
    return 0;
}

float hmc5883l_heading_from_xy(float x, float y)
{
    float ax;
    float ay;
    float base;
    float deg;

    if (x == 0.0f && y == 0.0f) {
        return 0.0f; /* 零向量：无方向可言，返回 0 而非 NaN */
    }

    /* 四象限 arctan 有理逼近（不引 math.h——裸机免链 libm，且纯函数可数值
     * 单测）：atan(z) ≈ z·P(z²)，z = |y/x| ∈ [0,1]，精度 ±0.01° 级 */
    ax = (x < 0.0f) ? -x : x;
    ay = (y < 0.0f) ? -y : y;
    if (ay <= ax) {
        float z = ay / ax;
        float z2 = z * z;
        base = z * (0.9998660f
                    - z2 * (0.3302995f
                            - z2 * (0.1801410f
                                    - z2 * (0.0851330f - z2 * 0.0208351f))));
    } else {
        float z = ax / ay;
        float z2 = z * z;
        base = 1.5707963f
               - z * (0.9998660f
                      - z2 * (0.3302995f
                              - z2 * (0.1801410f
                                      - z2 * (0.0851330f - z2 * 0.0208351f))));
    }
    /* 象限归位 */
    if (x < 0.0f) {
        base = 3.1415927f - base;
    }
    if (y < 0.0f) {
        base = -base;
    }

    deg = base * HMC5883L_RAD_TO_DEG;
    if (deg < 0.0f) {
        deg += 360.0f;
    }
    if (deg >= 360.0f) {
        deg -= 360.0f;
    }
    return deg;
}

uint8_t hmc5883l_read_heading(float *deg, int16_t x_off, int16_t y_off)
{
    int16_t x;
    int16_t y;
    int16_t z;

    if (hmc5883l_read(&x, &y, &z) != 0) {
        return 1;
    }
    if (deg != NULL) {
        /* 硬铁偏移按轴相减（z 不参与航向——只有 x/y 决定水平面方向） */
        *deg = hmc5883l_heading_from_xy((float)x - (float)x_off,
                                        (float)y - (float)y_off);
    }
    return 0;
}
