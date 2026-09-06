#include "jy61p.h"
#include "delay.h" /* delay_us / delay_ms：软 I2C 位操作与初始化序列 */
#include "ti_msp_dl_config.h" /* JY61P_PORT / JY61P_SCL_PIN / JY61P_SDA_PIN /
                                * JY61P_SCL_IOMUX / JY61P_SDA_IOMUX
                                * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX，
                                * 照 AHT10/SHT30 先例） */

/* JY61P 软 I2C 位操作原语（立创 bsp 同款时序归一为 sht30 同款：SCL 半周期
 * 5us ≈ 100kHz 级总线速度，JY61P 模块 IIC 规格裕量充足）。
 * SDA 方向切换：写 = 输出（SDA_OUT + 电平），读 = 输入（SDA_IN + 采样）。 */

#define JY61P_SDA_OUT()                                        \
    do {                                                       \
        DL_GPIO_initDigitalOutput(JY61P_SDA_IOMUX);            \
        DL_GPIO_setPins(JY61P_PORT, JY61P_SDA_PIN);            \
        DL_GPIO_enableOutput(JY61P_PORT, JY61P_SDA_PIN);       \
    } while (0)

#define JY61P_SDA_IN()                    \
    do {                                  \
        DL_GPIO_initDigitalInput(JY61P_SDA_IOMUX); \
    } while (0)

#define JY61P_SDA_GET() \
    ((DL_GPIO_readPins(JY61P_PORT, JY61P_SDA_PIN) & JY61P_SDA_PIN) ? 1 : 0)

#define JY61P_SDA(x)                                              \
    do {                                                          \
        if (x) {                                                  \
            DL_GPIO_setPins(JY61P_PORT, JY61P_SDA_PIN);           \
        } else {                                                  \
            DL_GPIO_clearPins(JY61P_PORT, JY61P_SDA_PIN);         \
        }                                                         \
    } while (0)

#define JY61P_SCL(x)                                              \
    do {                                                          \
        if (x) {                                                  \
            DL_GPIO_setPins(JY61P_PORT, JY61P_SCL_PIN);           \
        } else {                                                  \
            DL_GPIO_clearPins(JY61P_PORT, JY61P_SCL_PIN);         \
        }                                                         \
    } while (0)

static void jy61p_iic_start(void)
{
    JY61P_SDA_OUT();
    JY61P_SCL(1);
    JY61P_SDA(0);
    JY61P_SDA(1);
    delay_us(5);
    JY61P_SDA(0);
    delay_us(5);
    JY61P_SCL(0);
}

static void jy61p_iic_stop(void)
{
    JY61P_SDA_OUT();
    JY61P_SCL(0);
    JY61P_SDA(0);
    JY61P_SCL(1);
    delay_us(5);
    JY61P_SDA(1);
    delay_us(5);
}

static void jy61p_iic_send_ack(uint8_t ack)
{
    JY61P_SDA_OUT();
    JY61P_SCL(0);
    JY61P_SDA(0); /* 页面原式：先置 0，再按 ack 重设（ack=0 时同值二次写） */
    delay_us(5);
    if (!ack) {
        JY61P_SDA(0);
    } else {
        JY61P_SDA(1);
    }
    JY61P_SCL(1);
    delay_us(5);
    JY61P_SCL(0);
    JY61P_SDA(1);
}

static uint8_t jy61p_iic_wait_ack(void)
{
    uint8_t ack_flag = 10; /* 页面超时计数（页面 50×5us，归一为 sht30 同款 10） */

    /* 页面 I2C_WaitAck 在 while 轮询前未拉高 SCL（时序微瑕——SDA 采样须在
     * SCL 高电平窗口），本件照 sht20/sht30 正确版实现：先拉高 SCL 再采样，
     * 与页面行为等价（页面真机可用记录见 manifest notes） */
    JY61P_SCL(0);
    JY61P_SDA(1);
    JY61P_SDA_IN();
    JY61P_SCL(1);
    while ((JY61P_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        jy61p_iic_stop();
        return 1; /* 超时无应答 */
    }
    JY61P_SCL(0);
    JY61P_SDA_OUT();
    return 0;
}

static void jy61p_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    JY61P_SDA_OUT();
    JY61P_SCL(0);
    for (i = 0; i < 8; i++) {
        JY61P_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        JY61P_SCL(1);
        delay_us(5);
        JY61P_SCL(0);
        delay_us(5);
        dat <<= 1;
    }
}

static uint8_t jy61p_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    JY61P_SDA_IN();
    for (i = 0; i < 8; i++) {
        JY61P_SCL(0);
        delay_us(5);
        JY61P_SCL(1);
        delay_us(5);
        receive <<= 1;
        if (JY61P_SDA_GET()) {
            receive |= 1;
        }
        delay_us(5);
    }
    JY61P_SCL(0);
    return receive;
}

/* 寄存器写入（页面 writeDataJy61p 原样：START + 写地址 + 寄存器 + 数据
 * 逐字节应答）；返回 0 = 成功、1 = 任一应答失败。 */
static uint8_t jy61p_write_reg(uint8_t reg, const uint8_t *data, uint32_t len)
{
    uint32_t i;

    jy61p_iic_start();
    jy61p_iic_send_byte((uint8_t)((JY61P_ADDR << 1) | 0u)); /* 写地址 */
    if (jy61p_iic_wait_ack() == 1) {
        return 1;
    }
    jy61p_iic_send_byte(reg);
    if (jy61p_iic_wait_ack() == 1) {
        return 1;
    }
    for (i = 0; i < len; i++) {
        jy61p_iic_send_byte(data[i]);
        if (jy61p_iic_wait_ack() == 1) {
            return 1;
        }
    }
    jy61p_iic_stop();
    return 0;
}

/* 寄存器读取（页面 readDataJy61p 原样：START + 写地址 + 寄存器 + 重复
 * START + 读地址 + 逐字节读取，末字节 NACK + 停止）；返回 0 = 成功、
 * 1 = 任一应答失败。 */
static uint8_t jy61p_read_reg(uint8_t reg, uint8_t *data, uint32_t len)
{
    uint32_t i;

    jy61p_iic_start();
    jy61p_iic_send_byte((uint8_t)((JY61P_ADDR << 1) | 0u)); /* 写地址 */
    if (jy61p_iic_wait_ack() == 1) {
        return 1;
    }
    jy61p_iic_send_byte(reg);
    if (jy61p_iic_wait_ack() == 1) {
        return 1;
    }
    delay_us(5); /* 页面读前稳定拍 */

    jy61p_iic_start();
    jy61p_iic_send_byte((uint8_t)((JY61P_ADDR << 1) | 1u)); /* 读地址 */
    if (jy61p_iic_wait_ack() == 1) {
        return 1;
    }
    for (i = 0; i < len; i++) {
        data[i] = jy61p_iic_read_byte();
        if (i != (len - 1)) {
            jy61p_iic_send_ack(0);
        } else {
            jy61p_iic_send_ack(1); /* 末字节非应答（页面原样） */
        }
    }
    jy61p_iic_stop();
    return 0;
}

void jy61p_init(void)
{
    /* 页面 jy61pInit 初始化序列原样（每步 200ms——页面「官方建议 3s，
     * 实验 200ms 也行」取页面值；真机留验证） */
    static const uint8_t unlock_reg[2] = {0x88, 0xB5}; /* 寄存器写使能 */
    static const uint8_t z_axis_reg[2] = {0x04, 0x00}; /* Z 轴归零 */
    static const uint8_t angle_reg[2] = {0x08, 0x00};  /* 角度归零 */
    static const uint8_t save_reg[2] = {0x00, 0x00};   /* 保存 */

    /* Z 轴归零 */
    (void)jy61p_write_reg(JY61P_REG_UN, unlock_reg, 2);
    delay_ms(JY61P_INIT_DELAY_MS);
    (void)jy61p_write_reg(JY61P_REG_ANGLE_REFER, z_axis_reg, 2);
    delay_ms(JY61P_INIT_DELAY_MS);
    (void)jy61p_write_reg(JY61P_REG_SAVE, save_reg, 2);
    delay_ms(JY61P_INIT_DELAY_MS);

    /* 角度归零 */
    (void)jy61p_write_reg(JY61P_REG_UN, unlock_reg, 2);
    delay_ms(JY61P_INIT_DELAY_MS);
    (void)jy61p_write_reg(JY61P_REG_ANGLE_REFER, angle_reg, 2);
    delay_ms(JY61P_INIT_DELAY_MS);
    (void)jy61p_write_reg(JY61P_REG_SAVE, save_reg, 2);
    delay_ms(JY61P_INIT_DELAY_MS);
}

uint8_t jy61p_read_angles(float *roll_deg, float *pitch_deg, float *yaw_deg)
{
    uint8_t data[JY61P_ANGLE_BYTES] = {0};
    float roll_x;
    float pitch_y;
    float yaw_z;

    if (jy61p_read_reg(JY61P_REG_ROLL_LOW, data, JY61P_ANGLE_BYTES) != 0) {
        return 1;
    }

    /* 页面 get_angle 换算原式：raw/32768.0×180.0 + ±180° 回绕
     * （2 字节 LSB 先） */
    roll_x = (float)(((uint16_t)data[1] << 8) | data[0]) / 32768.0f * 180.0f;
    if (roll_x > 180.0f) {
        roll_x -= 360.0f;
    } else if (roll_x < -180.0f) {
        roll_x += 360.0f;
    }

    pitch_y = (float)(((uint16_t)data[3] << 8) | data[2]) / 32768.0f * 180.0f;
    if (pitch_y > 180.0f) {
        pitch_y -= 360.0f;
    } else if (pitch_y < -180.0f) {
        pitch_y += 360.0f;
    }

    yaw_z = (float)(((uint16_t)data[5] << 8) | data[4]) / 32768.0f * 180.0f;
    if (yaw_z > 180.0f) {
        yaw_z -= 360.0f;
    } else if (yaw_z < -180.0f) {
        yaw_z += 360.0f;
    }

    if (roll_deg != NULL) {
        *roll_deg = roll_x;
    }
    if (pitch_deg != NULL) {
        *pitch_deg = pitch_y;
    }
    if (yaw_deg != NULL) {
        *yaw_deg = yaw_z;
    }
    return 0;
}

uint8_t jy61p_read_raw(uint8_t data[JY61P_ANGLE_BYTES])
{
    return jy61p_read_reg(JY61P_REG_ROLL_LOW, data, JY61P_ANGLE_BYTES);
}
