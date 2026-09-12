/* 来源：QST（昆山东方微电子）QMC5883L 官方数据手册 QST-PD-B002-22
 * Rev. B《QMC5883L 三轴磁传感器》——https://www.qstcorp.com（3-Axis
 * Magnetic Sensor 器件页 PDF）。库内**无** lckfb 磁力计移植手册页（地猛星
 * 41 篇 / 地阔星 43 篇 sensor 页均无磁力计条目，已全库检索确认），故本件
 * 寄存器表依据 = 官方数据手册 + 仓库内既有 HMC5883L 实现
 * （库内与桌面工作目录遗留旧实现的缺陷清单）交叉核对。
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、引脚宏参数化等）。 */

#include "qmc5883l.h"
#include "delay.h" /* delay_ms：软复位后等待器件进 Standby、DRDY 轮询 */
#include "math.h"  /* atan2f：航向角换算（bmp180 编译先例） */
#include "ti_msp_dl_config.h" /* QMC5883L_PORT / QMC5883L_SCL_PIN /
                               * QMC5883L_SDA_PIN / QMC5883L_SCL_IOMUX /
                               * QMC5883L_SDA_IOMUX
                               * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX） */

/* QMC5883L 软 I2C 位操作原语（照 bh1750 先例：半周期 2us ≈ 100kHz 级，
 * QMC5883L 规格 Fast Mode ≤400kHz，裕量充足）。SDA 方向切换：写 = 输出
 * （QMC5883L_SDA_OUT + 电平），读 = 输入（QMC5883L_SDA_IN + 采样）。 */

#define QMC5883L_SDA_OUT()                                   \
    do {                                                     \
        DL_GPIO_initDigitalOutput(QMC5883L_SDA_IOMUX);       \
        DL_GPIO_setPins(QMC5883L_PORT, QMC5883L_SDA_PIN);    \
        DL_GPIO_enableOutput(QMC5883L_PORT, QMC5883L_SDA_PIN); \
    } while (0)

#define QMC5883L_SDA_IN()                                \
    do {                                                 \
        DL_GPIO_initDigitalInput(QMC5883L_SDA_IOMUX);    \
    } while (0)

#define QMC5883L_SDA_GET() \
    ((DL_GPIO_readPins(QMC5883L_PORT, QMC5883L_SDA_PIN) & QMC5883L_SDA_PIN) ? 1 : 0)

#define QMC5883L_SDA(level)                                      \
    do {                                                         \
        if (level) {                                             \
            DL_GPIO_setPins(QMC5883L_PORT, QMC5883L_SDA_PIN);    \
        } else {                                                 \
            DL_GPIO_clearPins(QMC5883L_PORT, QMC5883L_SDA_PIN);  \
        }                                                        \
    } while (0)

#define QMC5883L_SCL(level)                                      \
    do {                                                         \
        if (level) {                                             \
            DL_GPIO_setPins(QMC5883L_PORT, QMC5883L_SCL_PIN);    \
        } else {                                                 \
            DL_GPIO_clearPins(QMC5883L_PORT, QMC5883L_SCL_PIN);  \
        }                                                        \
    } while (0)

static void qmc5883l_iic_start(void)
{
    QMC5883L_SDA_OUT();
    QMC5883L_SDA(1);
    QMC5883L_SCL(1);
    delay_us(2);
    QMC5883L_SDA(0);
    delay_us(2);
    QMC5883L_SCL(0);
}

static void qmc5883l_iic_stop(void)
{
    QMC5883L_SDA_OUT();
    QMC5883L_SCL(0);
    QMC5883L_SDA(0);
    delay_us(2);
    QMC5883L_SCL(1);
    QMC5883L_SDA(1);
    delay_us(2);
}

/* ack 后置一位应答/非应答：is_nack = 0 应答（继续收下一字节）、1 = 非应答
 * （最后一字节，通知从机停发） */
static void qmc5883l_iic_send_ack(uint8_t is_nack)
{
    QMC5883L_SDA_OUT();
    QMC5883L_SCL(0);
    if (is_nack) {
        QMC5883L_SDA(1);
    } else {
        QMC5883L_SDA(0);
    }
    delay_us(2);
    QMC5883L_SCL(1);
    delay_us(2);
    QMC5883L_SCL(0);
    QMC5883L_SDA(1);
}

static uint8_t qmc5883l_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    QMC5883L_SDA(1);
    delay_us(1);
    QMC5883L_SCL(1);
    delay_us(1);
    QMC5883L_SDA_IN();
    delay_us(2);
    while ((QMC5883L_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(3);
    }
    if (ack_flag <= 0) {
        qmc5883l_iic_stop();
        return 1; /* 超时无应答 */
    }
    QMC5883L_SCL(0);
    QMC5883L_SDA_OUT();
    QMC5883L_SDA(0);
    return 0;
}

static void qmc5883l_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    QMC5883L_SDA_OUT();
    QMC5883L_SCL(0);
    for (i = 0; i < 8; i++) {
        QMC5883L_SDA((dat & 0x80) >> 7);
        delay_us(1);
        QMC5883L_SCL(1);
        delay_us(2);
        QMC5883L_SCL(0);
        delay_us(2);
        dat <<= 1;
    }
}

static uint8_t qmc5883l_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    QMC5883L_SDA_IN();
    for (i = 0; i < 8; i++) {
        QMC5883L_SCL(0);
        delay_us(2);
        QMC5883L_SCL(1);
        delay_us(2);
        receive <<= 1;
        if (QMC5883L_SDA_GET()) {
            receive |= 1;
        }
        delay_us(1);
    }
    QMC5883L_SCL(0);
    return receive;
}

/* 写一字节寄存器：起始 → 从机地址+写（0x0D）→ 寄存器地址 → 数据 → 停止；
 * 返回 0=成功、1=无应答 */
static uint8_t qmc5883l_write_reg(uint8_t reg, uint8_t dat)
{
    qmc5883l_iic_start();
    qmc5883l_iic_send_byte(QMC5883L_ADDR_WRITE);
    if (qmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    qmc5883l_iic_send_byte(reg);
    if (qmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    qmc5883l_iic_send_byte(dat);
    if (qmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    qmc5883l_iic_stop();
    return 0;
}

/* 读 len 字节寄存器：起始 → 地址+写 → 寄存器地址 → 重启 → 地址+读（0x0E）
 * → 逐字节读 + 应答（末字节非应答）→ 停止（手册 §8.2.4 两阶段读序列）；
 * 返回 0=成功、1=无应答 */
static uint8_t qmc5883l_read_regs(uint8_t reg, uint8_t *buf, uint8_t len)
{
    uint8_t i;

    qmc5883l_iic_start();
    qmc5883l_iic_send_byte(QMC5883L_ADDR_WRITE);
    if (qmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    qmc5883l_iic_send_byte(reg);
    if (qmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    qmc5883l_iic_start(); /* 重启：读阶段（手册表 11） */
    qmc5883l_iic_send_byte(QMC5883L_ADDR_READ);
    if (qmc5883l_iic_wait_ack() != 0) {
        return 1;
    }
    for (i = 0; i < len; i++) {
        buf[i] = qmc5883l_iic_read_byte();
        qmc5883l_iic_send_ack((uint8_t)((i == (uint8_t)(len - 1)) ? 1 : 0));
    }
    qmc5883l_iic_stop();
    return 0;
}

/* 等状态寄存器 DRDY（0x06 bit0；手册 §9.2.2：三轴数据就绪时置位，读任一数据
 * 寄存器后清零）。超时返回 1（调用方仍照现状读一次——器件 10Hz 刷新，超时
 * 多为上一轮数据，宁给旧值也不返回失败）。 */
static uint8_t qmc5883l_wait_drdy(void)
{
    uint8_t status = 0;
    uint8_t wait = QMC5883L_DRDY_TIMEOUT_MS;

    while (wait > 0) {
        if (qmc5883l_read_regs(QMC5883L_REG_STATUS, &status, 1) != 0) {
            return 1;
        }
        if ((status & QMC5883L_STATUS_DRDY) != 0) {
            return 0;
        }
        wait--;
        delay_ms(1);
    }
    return 1;
}

uint8_t qmc5883l_init(void)
{
    uint8_t id = 0;

    /* 软复位（控制2 bit7）：恢复全部寄存器默认值（MODE=Standby），手册
     * §9.2.4；等器件就绪再验 ID——手册 §9.2.6 明示 Chip ID 寄存器读回 0xFF */
    if (qmc5883l_write_reg(QMC5883L_REG_CTRL2, QMC5883L_CTRL2_RESET) != 0) {
        return 1; /* 总线无应答：器件没接/接线错/无上拉 */
    }
    delay_ms(QMC5883L_RESET_WAIT_MS);
    if (qmc5883l_read_regs(QMC5883L_REG_CHIP_ID, &id, 1) != 0) {
        return 1;
    }
    if (id != QMC5883L_CHIP_ID) {
        return 2; /* 器件 ID 不符：接错型号（HMC/QMC 互换）或器件无应答 */
    }

    /* SET/RESET 周期（手册 §9.2.5：推荐寄存器 0x0B 写 0x01） */
    if (qmc5883l_write_reg(QMC5883L_REG_FBR, QMC5883L_FBR_PERIOD) != 0) {
        return 1;
    }
    /* 控制1：OSR=512 / RNG=±8G / ODR=10Hz / 连续测量（手册表 16） */
    if (qmc5883l_write_reg(QMC5883L_REG_CTRL1, QMC5883L_CTRL1_VALUE) != 0) {
        return 1;
    }
    /* 控制2：开指针翻转（连续读 0x00~0x06 一次取齐）、不开中断脚 */
    if (qmc5883l_write_reg(QMC5883L_REG_CTRL2, QMC5883L_CTRL2_VALUE) != 0) {
        return 1;
    }
    return 0;
}

uint8_t qmc5883l_read(int16_t *x, int16_t *y, int16_t *z)
{
    uint8_t buf[QMC5883L_DATA_LEN];

    (void)qmc5883l_wait_drdy(); /* 等新数据（超时按现状读） */
    if (qmc5883l_read_regs(QMC5883L_REG_DATA, buf, QMC5883L_DATA_LEN) != 0) {
        return 1; /* 读失败：出参保持原值 */
    }
    /* 手册 §9.2.1：X 低/高（0x00/0x01）、Y（0x02/0x03）、Z（0x04/0x05），
     * 每轴 16 位**小端**、补码有符号（MSB 位为符号位） */
    if (x != NULL) {
        *x = (int16_t)(((uint16_t)buf[1] << 8) | (uint16_t)buf[0]);
    }
    if (y != NULL) {
        *y = (int16_t)(((uint16_t)buf[3] << 8) | (uint16_t)buf[2]);
    }
    if (z != NULL) {
        *z = (int16_t)(((uint16_t)buf[5] << 8) | (uint16_t)buf[4]);
    }
    return 0;
}

float qmc5883l_heading_from_xy(float x, float y)
{
    float deg;

    /* 零向量（含 IEEE-754 的 -0.0 形式）：无方向可言，直接返回 0——否则
     * atan2f 会按 x 的符号位给出 0/180 两种结果（-0.0 判为 π） */
    if ((x == 0.0f) && (y == 0.0f)) {
        return 0.0f;
    }
    /* 航向（顺时针，0–360°）= atan2(东向分量 y, 北向分量 x) 折算成度 */
    deg = atan2f(y, x) * 57.29578f; /* 180/π */
    while (deg < 0.0f) {
        deg += 360.0f;
    }
    while (deg >= 360.0f) {
        deg -= 360.0f;
    }
    return deg;
}

uint8_t qmc5883l_read_heading(float *deg, int16_t x_off, int16_t y_off)
{
    int16_t x = 0;
    int16_t y = 0;
    int16_t z = 0;

    if (qmc5883l_read(&x, &y, &z) != 0) {
        return 1; /* 出参保持原值 */
    }
    if (deg != NULL) {
        *deg = qmc5883l_heading_from_xy((float)x - (float)x_off,
                                        (float)y - (float)y_off);
    }
    return 0;
}
