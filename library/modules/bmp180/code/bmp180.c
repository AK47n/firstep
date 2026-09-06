/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《BMP180气压传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/bmp180-pressure-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "bmp180.h"
#include "delay.h" /* delay_us / delay_ms：软 I2C 位操作与读应答重试 */
#include "math.h"  /* pow：海拔换算（ir_distance 先例） */
#include "ti_msp_dl_config.h" /* BMP180_PORT / BMP180_SCL_PIN / BMP180_SDA_PIN /
                                * BMP180_SCL_IOMUX / BMP180_SDA_IOMUX
                                * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX，
                                * 编译矩阵实测；照 AHT10 先例） */

/* BMP180 软 I2C 位操作原语（立创 bsp 同款时序：SCL 半周期 5us ≈ 100kHz 级
 * 总线速度；SDA 方向切换：写 = 输出（SDA_OUT + 电平），读 = 输入
 * （SDA_IN + 采样）——sht30 同款宏）。 */

#define BMP180_SDA_OUT()                                        \
    do {                                                       \
        DL_GPIO_initDigitalOutput(BMP180_SDA_IOMUX);           \
        DL_GPIO_setPins(BMP180_PORT, BMP180_SDA_PIN);          \
        DL_GPIO_enableOutput(BMP180_PORT, BMP180_SDA_PIN);     \
    } while (0)

#define BMP180_SDA_IN() \
    do {                \
        DL_GPIO_initDigitalInput(BMP180_SDA_IOMUX); \
    } while (0)

#define BMP180_SDA_GET() \
    ((DL_GPIO_readPins(BMP180_PORT, BMP180_SDA_PIN) & BMP180_SDA_PIN) ? 1 : 0)

#define BMP180_SDA(x)                                              \
    do {                                                           \
        if (x) {                                                   \
            DL_GPIO_setPins(BMP180_PORT, BMP180_SDA_PIN);          \
        } else {                                                   \
            DL_GPIO_clearPins(BMP180_PORT, BMP180_SDA_PIN);        \
        }                                                          \
    } while (0)

#define BMP180_SCL(x)                                              \
    do {                                                           \
        if (x) {                                                   \
            DL_GPIO_setPins(BMP180_PORT, BMP180_SCL_PIN);          \
        } else {                                                   \
            DL_GPIO_clearPins(BMP180_PORT, BMP180_SCL_PIN);        \
        }                                                          \
    } while (0)

/* 校准系数（页面 _BMP180_PARAM_ + param 全局收敛为模块静态） */
typedef struct {
    int16_t ac1;
    int16_t ac2;
    int16_t ac3;
    uint16_t ac4;
    uint16_t ac5;
    uint16_t ac6;
    int16_t b1;
    int16_t b2;
    int16_t mb;
    int16_t mc;
    int16_t md;
} bmp180_cal_t;

static bmp180_cal_t bmp180_cal;
static long bmp180_b5 = 0; /* 温度段中间量 B5——气压段复用（页面全局 B5
                            * 收敛模块静态；页面 Get_Pressure 内嵌重复调
                            * Get_Temperature 的二次读取省去，结果等价） */

static void bmp180_iic_start(void)
{
    BMP180_SDA_OUT();
    BMP180_SDA(1);
    delay_us(5);
    BMP180_SCL(1);
    delay_us(5);
    BMP180_SDA(0);
    delay_us(5);
    BMP180_SCL(0);
    delay_us(5);
}

static void bmp180_iic_stop(void)
{
    BMP180_SDA_OUT();
    BMP180_SCL(0);
    BMP180_SDA(0);
    BMP180_SCL(1);
    delay_us(5);
    BMP180_SDA(1);
    delay_us(5);
}

static void bmp180_iic_send_ack(uint8_t ack)
{
    BMP180_SDA_OUT();
    BMP180_SCL(0);
    BMP180_SDA(0);
    delay_us(5);
    if (!ack) {
        BMP180_SDA(0);
    } else {
        BMP180_SDA(1);
    }
    BMP180_SCL(1);
    delay_us(5);
    BMP180_SCL(0);
    BMP180_SDA(1);
}

/* 等待从机应答（页面 I2C_WaitAck：先拉高 SCL 再采样——正确版（jy61p 页面
 * 微瑕对照），无需修正；返回 0 = 有应答、1 = 超时无应答（页面 10×5us）） */
static uint8_t bmp180_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;

    BMP180_SCL(0);
    BMP180_SDA(1);
    BMP180_SDA_IN();
    delay_us(5);
    BMP180_SCL(1);
    delay_us(5);
    while ((BMP180_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        bmp180_iic_stop();
        return 1; /* 超时无应答 */
    }
    BMP180_SCL(0);
    BMP180_SDA_OUT();
    return 0;
}

static void bmp180_iic_send_byte(uint8_t dat)
{
    uint8_t i;

    BMP180_SDA_OUT();
    BMP180_SCL(0); /* 拉低时钟开始数据传输 */
    for (i = 0; i < 8; i++) {
        BMP180_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        BMP180_SCL(1);
        delay_us(5);
        BMP180_SCL(0);
        delay_us(5);
        dat <<= 1;
    }
}

static uint8_t bmp180_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;

    BMP180_SDA_IN(); /* SDA 设置为输入 */
    for (i = 0; i < 8; i++) {
        BMP180_SCL(0);
        delay_us(5);
        BMP180_SCL(1);
        delay_us(5);
        receive <<= 1;
        if (BMP180_SDA_GET()) {
            receive |= 1;
        }
        delay_us(5);
    }
    BMP180_SCL(0);
    return receive;
}

/* 向 BMP180 写入一个字节（页面 BMP180_Write_Cmd 原式 + NACK printf 改状态
 * 码）：返回 0 = 成功、1/2/3 = 器件地址/寄存器地址/命令无应答（页面
 * "Write_Cmd NACK -1/-2/-3"） */
static uint8_t bmp180_write_cmd(uint8_t regaddr, uint8_t cmd)
{
    bmp180_iic_start(); /* 起始信号 */
    bmp180_iic_send_byte(BMP180_ADDR_W); /* 器件地址+写 */
    if (bmp180_iic_wait_ack() == 1) {
        return 1;
    }
    bmp180_iic_send_byte(regaddr);
    if (bmp180_iic_wait_ack() == 1) {
        return 2;
    }
    bmp180_iic_send_byte(cmd);
    if (bmp180_iic_wait_ack() == 1) {
        return 3;
    }
    bmp180_iic_stop();
    return 0;
}

/* 读取 BMP180 数据（页面 BMP180_Read16 原式：len==2 回 16bit、len==3
 * `(d0<<16|d1<<8|d2)>>8`（oss=0 时与标准 `>>(8-oss)` 一致——按页面保留）；
 * 逐字节重发写地址，读地址应答重试 ≤5×1ms（页面 timeout<5）保留；NACK
 * printf 改状态码）。返回 0 = 成功、1 = 器件地址无应答、2 = 寄存器地址
 * 无应答、3 = 读地址应答超时（>5×1ms）；成功时经 *out 带回。 */
static uint8_t bmp180_read16(uint16_t regaddr, uint8_t len, uint16_t *out)
{
    int timeout = 0;
    uint16_t dat[3] = {0};
    uint8_t ack_ok = 0;
    int i;

    for (i = 0; i < len; i++) {
        bmp180_iic_start(); /* 起始信号 */
        bmp180_iic_send_byte(BMP180_ADDR_W); /* 器件地址+写 */
        if (bmp180_iic_wait_ack() == 1) {
            return 1;
        }
        bmp180_iic_send_byte((uint8_t)(regaddr + i));
        if (bmp180_iic_wait_ack() == 1) {
            return 2;
        }

        ack_ok = 0;
        do {
            timeout++;
            delay_ms(1);
            bmp180_iic_start(); /* 起始信号 */
            bmp180_iic_send_byte(BMP180_ADDR_R); /* 器件地址+读 */
            if (bmp180_iic_wait_ack() == 0) {
                ack_ok = 1;
                break;
            }
        } while (timeout < 5);

        if (ack_ok == 0) {
            return 3; /* 读地址应答超时（页面 ≤5×1ms——timeout<5 出口含
                       * 第 5 次成功，按页面保留） */
        }

        dat[i] = bmp180_iic_read_byte();
        bmp180_iic_send_ack(1);
        bmp180_iic_stop();
        delay_ms(1);
    }
    if (len == 2) {
        *out = (uint16_t)((dat[0] << 8) | dat[1]);
    } else if (len == 3) {
        *out = (uint16_t)(((dat[0] << 16) | (dat[1] << 8) | (dat[2])) >> 8);
    } else {
        *out = 0;
    }
    return 0;
}

uint8_t bmp180_init(void)
{
    uint16_t v = 0;
    /* 页面 BMP180_Get_param 序列原式：0xAA..0xBE 逐项 Read16 */
    if (bmp180_read16(0xaa, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.ac1 = (int16_t)v;
    if (bmp180_read16(0xac, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.ac2 = (int16_t)v;
    if (bmp180_read16(0xae, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.ac3 = (int16_t)v;
    if (bmp180_read16(0xb0, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.ac4 = v;
    if (bmp180_read16(0xb2, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.ac5 = v;
    if (bmp180_read16(0xb4, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.ac6 = v;
    if (bmp180_read16(0xb6, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.b1 = (int16_t)v;
    if (bmp180_read16(0xb8, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.b2 = (int16_t)v;
    if (bmp180_read16(0xba, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.mb = (int16_t)v;
    if (bmp180_read16(0xbc, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.mc = (int16_t)v;
    if (bmp180_read16(0xbe, 2, &v) != 0) {
        return 1;
    }
    bmp180_cal.md = (int16_t)v;
    return 0;
}

/* 温度段（页面 BMP180_Get_Temperature 原式：0xF4←0x2E → 6ms → 0xF6 2 字节）
 * 返回 0 = 成功、1 = 温度段失败；temp_c 出参可 NULL。 */
static uint8_t bmp180_read_temp(float *temp_c)
{
    long ut = 0;
    long x1 = 0;
    long x2 = 0;
    uint16_t raw = 0;

    if (bmp180_write_cmd(BMP180_REG_CTRL_MEAS, BMP180_CMD_TEMP) != 0) {
        return 1;
    }
    delay_ms(6);
    if (bmp180_read16(0xf6, 2, &raw) != 0) {
        return 1;
    }
    ut = (long)raw;

    x1 = ((long)ut - bmp180_cal.ac6) * bmp180_cal.ac5 / 32768.0;
    x2 = ((long)bmp180_cal.mc * 2048.0) / (x1 + bmp180_cal.md);
    bmp180_b5 = x1 + x2;
    if (temp_c != NULL) {
        *temp_c = (float)(((bmp180_b5 + 8) / 16.0) * 0.1f);
    }
    return 0;
}

uint8_t bmp180_read(float *temp_c, float *pa)
{
    long up = 0;
    long x1 = 0;
    long x2 = 0;
    int32_t x3 = 0;
    int32_t b3 = 0;
    int32_t b4 = 0;
    int32_t b6 = 0;
    uint32_t b7 = 0;
    int32_t p = 0;
    uint16_t raw = 0;

    /* 温度段（页面原式；B5 进模块静态供气压段复用） */
    if (bmp180_read_temp(temp_c) != 0) {
        return 1;
    }

    /* 气压段（页面 BMP180_Get_Pressure 原式——B5 复用页面
     * Get_Temperature 内嵌调用的结果） */
    if (bmp180_write_cmd(BMP180_REG_CTRL_MEAS,
                         (uint8_t)(BMP180_CMD_PRES + (BMP180_OSS << 6))) != 0) {
        return 2;
    }
    delay_ms(10);
    if (bmp180_read16(0xf6, 3, &raw) != 0) {
        return 2;
    }
    up = (long)raw;

    b6 = (int32_t)(bmp180_b5 - 4000);

    x1 = (b6 * b6 >> 12) * bmp180_cal.b2 >> 11;
    x2 = bmp180_cal.ac2 * b6 >> 11;
    x3 = (int32_t)(x1 + x2);

    b3 = (((bmp180_cal.ac1 << 2) + x3) + 2) >> 2;

    x1 = bmp180_cal.ac3 * b6 >> 13;
    x2 = (b6 * b6 >> 12) * bmp180_cal.b1 >> 16;
    x3 = (int32_t)((x1 + x2 + 2) >> 2);

    b4 = (int32_t)(bmp180_cal.ac4 * (uint32_t)(x3 + 32768) >> 15);

    b7 = ((uint32_t)up - (uint32_t)b3) * 50000u;

    /* page 原式保留（B7 uint32_t——页面声明；**标准 BMP180 实现用 long B7
     * 并保留真/假双分支——B7 = ((uint32)UP−(uint32)B3)×50000，高 UP/负 B3
     * 时可达 ≥2^31，else 分支不可删**；oss=0 时 `(B7<<1)/B4` ≡ 标准
     * `(B7*2)/B4`、`B7/B4<<1` 优先级按页面——人工复核记录，notes 标注） */
    if (b7 < 0x80000000u) {
        p = (int32_t)((b7 << 1) / (uint32_t)b4);
    } else {
        p = (int32_t)((b7 / (uint32_t)b4) << 1);
    }

    x1 = (p >> 8) * (p >> 8);
    x1 = (x1 * 3038) >> 16;
    x2 = (-7375 * p) >> 16;
    p = p + (int32_t)((x1 + x2 + 3791) >> 4);

    if (pa != NULL) {
        *pa = (float)p;
    }
    return 0;
}

float bmp180_read_altitude(float pa)
{
    /* 页面 BMP180_Get_Altitude 原式（PRESSURE_OF_SEA = 101325.0f 参考海平面
     * 压强注释保留为公式常量） */
    return 44330.0f * (1.0f - (float)pow(pa / 101325.0, 1.0 / 5.255));
}
