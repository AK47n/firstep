/* 来源：Honeywell HMC5883L 三轴数字磁力计数据手册（Datasheet 900405 Rev E）。
 * 库内旧实现 ml_hmc5883l 的确定性缺陷清单见 hmc5883l_stm32.h / manifest notes
 * ——本文件是重写。 */

#include "hmc5883l_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 软 I2C 位操作原语（照 bh1750_stm32 先例：SCL 半周期 5us ≈ 100kHz 级；
 * 电平 = 开漏输出 OUT_OD + 上拉输入 IU——总线需板上/模块自带上拉；
 * **SCL 必须在 init 里 gpio_init + 置高**：库内曾有「SCL 从未初始化导致
 * 总线必死」的真 bug（wiki-stm32-batch2 回修），测试有对应守卫）。 */
#define HMC5883L_SDA_OUT() gpio_init(HMC5883L_SDA_GPIO, HMC5883L_SDA_PIN, OUT_OD)
#define HMC5883L_SDA_IN() gpio_init(HMC5883L_SDA_GPIO, HMC5883L_SDA_PIN, IU)
#define HMC5883L_SDA_GET() gpio_get(HMC5883L_SDA_GPIO, HMC5883L_SDA_PIN)
#define HMC5883L_SDA(x) gpio_set(HMC5883L_SDA_GPIO, HMC5883L_SDA_PIN, (x))
#define HMC5883L_SCL(x) gpio_set(HMC5883L_SCL_GPIO, HMC5883L_SCL_PIN, (x))

static void hmc5883l_iic_start(void)
{
    HMC5883L_SDA_OUT();
    HMC5883L_SDA(1);
    HMC5883L_SCL(1);
    delay_us(5);
    HMC5883L_SDA(0);
    delay_us(5);
    HMC5883L_SCL(0);
    delay_us(5);
}

static void hmc5883l_iic_stop(void)
{
    HMC5883L_SDA_OUT();
    HMC5883L_SCL(0);
    HMC5883L_SDA(0);
    HMC5883L_SCL(1);
    delay_us(5);
    HMC5883L_SDA(1);
    delay_us(5);
}

/* is_nack = 0 应答（继续收）、1 = 非应答（最后一字节） */
static void hmc5883l_iic_send_ack(uint8_t is_nack)
{
    HMC5883L_SDA_OUT();
    HMC5883L_SCL(0);
    HMC5883L_SDA(0);
    delay_us(5);
    if (is_nack) {
        HMC5883L_SDA(1);
    } else {
        HMC5883L_SDA(0);
    }
    HMC5883L_SCL(1);
    delay_us(5);
    HMC5883L_SCL(0);
    HMC5883L_SDA(1);
}

static uint8_t hmc5883l_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    HMC5883L_SCL(0);
    HMC5883L_SDA(1);
    HMC5883L_SDA_IN();
    delay_us(5);
    HMC5883L_SCL(1);
    delay_us(5);
    while ((HMC5883L_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        hmc5883l_iic_stop();
        return 1; /* 超时无应答 */
    }
    HMC5883L_SCL(0);
    HMC5883L_SDA_OUT();
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
        delay_us(5);
        HMC5883L_SCL(0);
        delay_us(5);
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
        delay_us(5);
        HMC5883L_SCL(1);
        delay_us(5);
        receive <<= 1;
        if (HMC5883L_SDA_GET()) {
            receive |= 1;
        }
        delay_us(5);
    }
    HMC5883L_SCL(0);
    return receive;
}

/* 写寄存器：起始 → 写地址 → 寄存器 → 数据 → 应答 → 停止；0=成功 1=无应答 */
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

/* 连续读：写地址定寄存器 → 重启 → 读地址 → 逐字节（前 n-1 应答、末字节非
 * 应答）→ 停止；两处读地址应答都检查（旧实现缺陷①：ADDR | 0x01 当寄存器） */
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

uint8_t hmc5883l_init(void)
{
    uint8_t id[3];

    /* 先初始化两脚（SCL 必须 gpio_init + 置高——见上方批次 3 回修说明），
     * 总线空闲后再验 ID */
    gpio_init(HMC5883L_SCL_GPIO, HMC5883L_SCL_PIN, OUT_OD);
    gpio_init(HMC5883L_SDA_GPIO, HMC5883L_SDA_PIN, OUT_OD);
    HMC5883L_SCL(1);
    HMC5883L_SDA(1);

    if (hmc5883l_read_regs(HMC5883L_REG_ID_A, id, 3) != 0) {
        return 1; /* 总线无应答 */
    }
    if (id[0] != HMC5883L_ID_A_VALUE || id[1] != HMC5883L_ID_B_VALUE
        || id[2] != HMC5883L_ID_C_VALUE) {
        return 2; /* 型号不符（多为 QMC5883L） */
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
    /* 数据区顺序 = X(0x03/04)、Z(0x05/06)、Y(0x07/08)——非 X-Y-Z */
    if (x != 0) {
        *x = (int16_t)(((uint16_t)buf[0] << 8) | (uint16_t)buf[1]);
    }
    if (z != 0) {
        *z = (int16_t)(((uint16_t)buf[2] << 8) | (uint16_t)buf[3]);
    }
    if (y != 0) {
        *y = (int16_t)(((uint16_t)buf[4] << 8) | (uint16_t)buf[5]);
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
        return 0.0f; /* 零向量：返回 0 而非 NaN */
    }

    /* 四象限 arctan 有理逼近（不引 math.h——F1 工程免链 libm） */
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
    if (deg != 0) {
        *deg = hmc5883l_heading_from_xy((float)x - (float)x_off,
                                        (float)y - (float)y_off);
    }
    return 0;
}
