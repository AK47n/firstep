/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AHT10温湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/aht10-temp-humi-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "aht10.h"
#include "delay.h" /* delay_us / delay_ms：软 I2C 位操作与等待延时 */
#include "ti_msp_dl_config.h" /* AHT10_PORT / AHT10_SCL_PIN / AHT10_SDA_PIN /
                               * AHT10_SCL_IOMUX / AHT10_SDA_IOMUX
                               * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX，
                               * 编译矩阵实测；照 KEY_PIN_21_IOMUX 先例） */

/* AHT10 软 I2C 位操作原语（立创 bsp 同款时序：SCL 半周期 2us = 100kHz 级
 * 总线速度，AHT10 规格 ≤400kHz，裕量充足）。
 * SDA 方向切换：写 = 输出（SDA_OUT + 电平），读 = 输入（SDA_IN + 采样）。 */

#define AHT10_SDA_OUT()                                        \
    do {                                                       \
        DL_GPIO_initDigitalOutput(AHT10_SDA_IOMUX);            \
        DL_GPIO_setPins(AHT10_PORT, AHT10_SDA_PIN);            \
        DL_GPIO_enableOutput(AHT10_PORT, AHT10_SDA_PIN);       \
    } while (0)

#define AHT10_SDA_IN()                    \
    do {                                  \
        DL_GPIO_initDigitalInput(AHT10_SDA_IOMUX); \
    } while (0)

#define AHT10_SDA_GET() \
    ((DL_GPIO_readPins(AHT10_PORT, AHT10_SDA_PIN) & AHT10_SDA_PIN) ? 1 : 0)

#define AHT10_SDA(x)                                              \
    do {                                                          \
        if (x) {                                                  \
            DL_GPIO_setPins(AHT10_PORT, AHT10_SDA_PIN);           \
        } else {                                                  \
            DL_GPIO_clearPins(AHT10_PORT, AHT10_SDA_PIN);         \
        }                                                         \
    } while (0)

#define AHT10_SCL(x)                                              \
    do {                                                          \
        if (x) {                                                  \
            DL_GPIO_setPins(AHT10_PORT, AHT10_SCL_PIN);           \
        } else {                                                  \
            DL_GPIO_clearPins(AHT10_PORT, AHT10_SCL_PIN);         \
        }                                                         \
    } while (0)

static void aht10_iic_start(void)
{
    AHT10_SDA_OUT();
    AHT10_SDA(1);
    AHT10_SCL(1);
    delay_us(4);
    AHT10_SDA(0);
    delay_us(4);
    AHT10_SCL(0);
}

static void aht10_iic_stop(void)
{
    AHT10_SDA_OUT();
    AHT10_SCL(0);
    AHT10_SDA(0);
    delay_us(4);
    AHT10_SCL(1);
    AHT10_SDA(1);
    delay_us(4);
}

static void aht10_iic_send_ack(uint8_t ack)
{
    AHT10_SDA_OUT();
    AHT10_SCL(0);
    AHT10_SDA(0);
    delay_us(2);
    if (!ack) {
        AHT10_SDA(0);
    } else {
        AHT10_SDA(1);
    }
    AHT10_SCL(1);
    delay_us(2);
    AHT10_SCL(0);
    AHT10_SDA(1);
}

static uint8_t aht10_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    AHT10_SDA(1);
    delay_us(1);
    AHT10_SCL(1);
    delay_us(1);
    AHT10_SDA_IN();
    delay_us(2);
    while ((AHT10_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(3);
    }
    if (ack_flag <= 0) {
        aht10_iic_stop();
        return 1; /* 超时无应答 */
    }
    AHT10_SCL(0);
    AHT10_SDA_OUT();
    AHT10_SDA(0);
    return 0;
}

static void aht10_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    AHT10_SDA_OUT();
    AHT10_SCL(0);
    for (i = 0; i < 8; i++) {
        AHT10_SDA((dat & 0x80) >> 7);
        delay_us(1);
        AHT10_SCL(1);
        delay_us(2);
        AHT10_SCL(0);
        delay_us(2);
        dat <<= 1;
    }
}

static uint8_t aht10_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    AHT10_SDA_IN();
    for (i = 0; i < 8; i++) {
        AHT10_SCL(0);
        delay_us(2);
        AHT10_SCL(1);
        delay_us(2);
        receive <<= 1;
        if (AHT10_SDA_GET()) {
            receive |= 1;
        }
        delay_us(1);
    }
    AHT10_SCL(0);
    return receive;
}

void aht10_init(void)
{
    delay_ms(50); /* 上电/复位后等待稳定 */
    aht10_iic_start();
    aht10_iic_send_byte(0x70); /* 器件地址 0x38 << 1 + 写 */
    aht10_iic_wait_ack();
    aht10_iic_send_byte(0xE1); /* 软复位（立创发校准命令前的保底动作） */
    aht10_iic_wait_ack();
    aht10_iic_send_byte(0x08); /* 校准使能 */
    aht10_iic_wait_ack();
    aht10_iic_send_byte(0x00);
    aht10_iic_wait_ack();
    aht10_iic_stop();
    delay_ms(50);
}

uint8_t aht10_read(float *temperature_c, float *humidity_rh)
{
    uint8_t buff[6] = {0};
    uint8_t timeout = 0;
    uint32_t dat;
    uint8_t i;

    /* 触发测量：0xAC 0x33 0x00（0x33 = 湿度/温度都测 + NORMAL 模式） */
    aht10_iic_start();
    aht10_iic_send_byte(0x38 << 1 | 0);
    aht10_iic_wait_ack();
    aht10_iic_send_byte(0xAC);
    aht10_iic_wait_ack();
    aht10_iic_send_byte(0x33);
    aht10_iic_wait_ack();
    aht10_iic_send_byte(0x00);
    aht10_iic_wait_ack();
    aht10_iic_stop();

    /* 等采集完成：重发读地址直到有应答（最多 5 次 ×1ms；规格 ≥80ms，这里
     * 按立创原版 1ms 轮询上限 ×5 保底，读之前再等一次 80ms 失败也返回 1） */
    delay_ms(20);
    for (timeout = 0; timeout < 5; timeout++) {
        delay_ms(1);
        aht10_iic_start();
        aht10_iic_send_byte(0x38 << 1 | 1);
        if (aht10_iic_wait_ack() == 0) {
            break;
        }
    }
    if (timeout >= 5) {
        return 1; /* 无应答，采集失败 */
    }

    for (i = 0; i < 6; i++) {
        buff[i] = aht10_iic_read_byte();
        aht10_iic_send_ack(i == 5 ? 1 : 0); /* 最后一字节非应答 */
    }
    aht10_iic_stop();
    delay_ms(20);

    /* 湿度 20 位：buff[1..3] 高 4 位；温度 20 位：buff[3] 低 4 位 + buff[4..5] */
    dat = ((uint32_t)buff[1] << 12) | ((uint32_t)buff[2] << 4) | ((uint32_t)buff[3] >> 4);
    if (humidity_rh != NULL) {
        *humidity_rh = (float)dat / 1048576.0f * 100.0f;
    }
    dat = ((uint32_t)(buff[3] & 0x0F) << 16) | ((uint32_t)buff[4] << 8) | buff[5];
    if (temperature_c != NULL) {
        *temperature_c = (float)dat / 1048576.0f * 200.0f - 50.0f;
    }
    return 0;
}

float aht10_read_temperature(void)
{
    float t = 0.0f, h = 0.0f;
    (void)aht10_read(&t, &h);
    return t;
}

float aht10_read_humidity(void)
{
    float t = 0.0f, h = 0.0f;
    (void)aht10_read(&t, &h);
    return h;
}
