#include "ms5611.h"
#include "delay.h" /* delay_us / delay_ms：软 I2C 位操作与 10ms 转换等待 */
#include "math.h"  /* pow：海拔换算（ir_distance 先例） */
#include "ti_msp_dl_config.h" /* MS5611_PORT / MS5611_SCL_PIN / MS5611_SDA_PIN /
                                * MS5611_SCL_IOMUX / MS5611_SDA_IOMUX
                                * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX，
                                * 编译矩阵实测；照 AHT10 先例） */

/* MS5611 软 I2C 位操作原语（立创 bsp 同款时序：SCL 半周期 5us ≈ 100kHz 级
 * 总线速度；SDA 方向切换：写 = 输出（SDA_OUT + 电平），读 = 输入
 * （SDA_IN + 采样）——bmp180/sht30 同款宏）。 */

#define MS5611_SDA_OUT()                                        \
    do {                                                       \
        DL_GPIO_initDigitalOutput(MS5611_SDA_IOMUX);           \
        DL_GPIO_setPins(MS5611_PORT, MS5611_SDA_PIN);          \
        DL_GPIO_enableOutput(MS5611_PORT, MS5611_SDA_PIN);     \
    } while (0)

#define MS5611_SDA_IN() \
    do {                \
        DL_GPIO_initDigitalInput(MS5611_SDA_IOMUX); \
    } while (0)

#define MS5611_SDA_GET() \
    ((DL_GPIO_readPins(MS5611_PORT, MS5611_SDA_PIN) & MS5611_SDA_PIN) ? 1 : 0)

#define MS5611_SDA(x)                                              \
    do {                                                           \
        if (x) {                                                   \
            DL_GPIO_setPins(MS5611_PORT, MS5611_SDA_PIN);          \
        } else {                                                   \
            DL_GPIO_clearPins(MS5611_PORT, MS5611_SDA_PIN);        \
        }                                                          \
    } while (0)

#define MS5611_SCL(x)                                              \
    do {                                                           \
        if (x) {                                                   \
            DL_GPIO_setPins(MS5611_PORT, MS5611_SCL_PIN);          \
        } else {                                                   \
            DL_GPIO_clearPins(MS5611_PORT, MS5611_SCL_PIN);        \
        }                                                          \
    } while (0)

/* 出厂校准值（页面 Cal_C1_6[8] 全局收敛模块静态）：[0]=厂家信息、
 * [1]~[6]=C1..C6 校准值、[7]=CRC */
static uint16_t ms5611_cal[MS5611_PROM_WORDS];

static void ms5611_iic_start(void)
{
    MS5611_SDA_OUT();
    MS5611_SDA(1);
    delay_us(5);
    MS5611_SCL(1);
    delay_us(5);
    MS5611_SDA(0);
    delay_us(5);
    MS5611_SCL(0);
    delay_us(5);
}

static void ms5611_iic_stop(void)
{
    MS5611_SDA_OUT();
    MS5611_SCL(0);
    MS5611_SDA(0);
    MS5611_SCL(1);
    delay_us(5);
    MS5611_SDA(1);
    delay_us(5);
}

static void ms5611_iic_send_ack(uint8_t ack)
{
    MS5611_SDA_OUT();
    MS5611_SCL(0);
    MS5611_SDA(0);
    delay_us(5);
    if (!ack) {
        MS5611_SDA(0);
    } else {
        MS5611_SDA(1);
    }
    MS5611_SCL(1);
    delay_us(5);
    MS5611_SCL(0);
    MS5611_SDA(1);
}

/* 等待从机应答（页面 I2C_WaitAck：先拉高 SCL 再采样——正确版；返回
 * 0 = 有应答、1 = 超时无应答（页面 10×5us）） */
static uint8_t ms5611_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;

    MS5611_SCL(0);
    MS5611_SDA(1);
    MS5611_SDA_IN();
    delay_us(5);
    MS5611_SCL(1);
    delay_us(5);
    while ((MS5611_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        ms5611_iic_stop();
        return 1; /* 超时无应答 */
    }
    MS5611_SCL(0);
    MS5611_SDA_OUT();
    return 0;
}

static void ms5611_iic_send_byte(uint8_t dat)
{
    uint8_t i;

    MS5611_SDA_OUT();
    MS5611_SCL(0); /* 拉低时钟开始数据传输 */
    for (i = 0; i < 8; i++) {
        MS5611_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        MS5611_SCL(1);
        delay_us(5);
        MS5611_SCL(0);
        delay_us(5);
        dat <<= 1;
    }
}

static uint8_t ms5611_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;

    MS5611_SDA_IN(); /* SDA 设置为输入 */
    for (i = 0; i < 8; i++) {
        MS5611_SCL(0);
        delay_us(5);
        MS5611_SCL(1);
        delay_us(5);
        receive <<= 1;
        if (MS5611_SDA_GET()) {
            receive |= 1;
        }
        delay_us(5);
    }
    MS5611_SCL(0);
    return receive;
}

/* 读 D1 气压 / D2 温度原始 24 位（页面 MS5611_Read_D1_D2 原式：
 * 写命令 → 10ms → 写 0x00 → 10ms → 读 3 字节 24bit；页面 NACK printf 改
 * 状态码——1 = 写地址无应答、2 = 命令无应答、3 = 二次写地址无应答、
 * 4 = 0x00 无应答、5 = 读地址无应答（页面 "D1 NACK -1..-5"）。页面 NACK
 * 只打印不中断——本件按状态码中断返回（数据有效性保证），notes 记录） */
static uint8_t ms5611_read_d1_d2(uint8_t regaddr, uint32_t *out)
{
    uint8_t buff[3] = {0};

    ms5611_iic_start(); /* 起始信号 */
    ms5611_iic_send_byte(MS5611_ADDR_W);
    if (ms5611_iic_wait_ack() == 1) {
        return 1;
    }
    ms5611_iic_send_byte(regaddr); /* 转换命令（OSR = 4096） */
    if (ms5611_iic_wait_ack() == 1) {
        return 2;
    }
    ms5611_iic_stop();

    delay_ms(MS5611_CONV_WAIT_MS);

    ms5611_iic_start(); /* 起始信号 */
    ms5611_iic_send_byte(MS5611_ADDR_W);
    if (ms5611_iic_wait_ack() == 1) {
        return 3;
    }
    ms5611_iic_send_byte(0x00); /* 读取数据请求 */
    if (ms5611_iic_wait_ack() == 1) {
        return 4;
    }
    ms5611_iic_stop();

    delay_ms(MS5611_CONV_WAIT_MS);

    ms5611_iic_start(); /* 起始信号 */
    ms5611_iic_send_byte(MS5611_ADDR_R);
    if (ms5611_iic_wait_ack() == 1) {
        return 5;
    }

    buff[0] = ms5611_iic_read_byte();
    ms5611_iic_send_ack(0);
    buff[1] = ms5611_iic_read_byte();
    ms5611_iic_send_ack(0);
    buff[2] = ms5611_iic_read_byte();
    ms5611_iic_send_ack(1);
    ms5611_iic_stop();

    *out = (uint32_t)(((uint32_t)buff[0] << 16) | ((uint32_t)buff[1] << 8) | buff[2]);
    return 0;
}

uint8_t ms5611_init(void)
{
    uint8_t data_h = 0;
    uint8_t data_l = 0;
    uint8_t i;

    /* 复位（页面 MS5611_Reset：0 = 成功、1 = 器件地址错误、2 = 命令无应答） */
    ms5611_iic_start(); /* 起始信号 */
    ms5611_iic_send_byte(MS5611_ADDR_W); /* 器件地址+写 */
    if (ms5611_iic_wait_ack() == 1) {
        return 1;
    }
    ms5611_iic_send_byte(MS5611_CMD_RESET);
    if (ms5611_iic_wait_ack() == 1) {
        return 2;
    }
    ms5611_iic_stop();

    delay_ms(MS5611_INIT_WAIT_MS); /* 页面「等待初始化完成」300ms */

    /* 读 PROM（页面 MS5611_Read_PROM 原式 8 字 0xA0..0xAE；**页面 PROM 读的
     * I2C_WaitAck 无应答检查缺漏——人工复核修正：逐段检查应答，任一无应答
     * 返回 3 = PROM 读应答失败**，notes 记录） */
    for (i = 0; i < MS5611_PROM_WORDS; i++) {
        ms5611_iic_start(); /* 起始信号 */
        ms5611_iic_send_byte(MS5611_ADDR_W);
        if (ms5611_iic_wait_ack() == 1) {
            return 3;
        }
        ms5611_iic_send_byte((uint8_t)(MS5611_PROM_BASE + i * 2));
        if (ms5611_iic_wait_ack() == 1) {
            return 3;
        }
        ms5611_iic_stop();

        delay_us(200);

        ms5611_iic_start(); /* 起始信号 */
        ms5611_iic_send_byte(MS5611_ADDR_R);
        if (ms5611_iic_wait_ack() == 1) {
            return 3;
        }

        data_h = ms5611_iic_read_byte(); /* 高 8 位 */
        ms5611_iic_send_ack(0);
        data_l = ms5611_iic_read_byte(); /* 低 8 位 */
        ms5611_iic_send_ack(1);
        ms5611_iic_stop();

        ms5611_cal[i] = (uint16_t)((uint16_t)data_h << 8) | data_l; /* 保存校准 */
    }
    return 0;
}

uint8_t ms5611_read(float *temp_c, float *pressure_pa)
{
    uint32_t d1 = 0;
    uint32_t d2 = 0;
    long long dT = 0; /* 页面声明 uint32_t——低于 20℃ 时 dT 为负、无符号回绕
                       * 破坏换算，且 C4×dT/128、C3×dT/256.0 在 32 位乘法会
                       * 有符号溢出（积可达 1e11 ≫ 2^31，全温区多数读数偏差
                       * 数十 hPa）——人工复核修正为有符号 64 位 long long
                       * （表达式不变，标准实现 int64 口径），notes 记录 */
    long long temp = 0;
    long long off = 0;
    long long sens = 0;
    long long p = 0;
    uint8_t st;

    /* 2 次转换按页面原式（Get_TEMP 序列：D1 = 0x48、D2 = 0x58——每段内部
     * 命令/数据请求各 10ms 等待 + **段间 10ms**（页面 Get_TEMP L384/386
     * 两次转换间各有 delay_ms(10)，本件按页面保留）；页面 Get_pressure
     * 内嵌重复调 Get_TEMP 的二次重读省去——单次 D1/D2 读取 + 一次全换算，
     * 结果等价（页面用全局 D1/D2/dT 复用），notes 记录） */
    st = ms5611_read_d1_d2(MS5611_CMD_D1, &d1);
    if (st == 5) {
        return 3; /* 数据读失败（读地址无应答） */
    }
    if (st != 0) {
        return 1; /* D1 段失败 */
    }
    delay_ms(MS5611_CONV_WAIT_MS);
    st = ms5611_read_d1_d2(MS5611_CMD_D2, &d2);
    if (st == 5) {
        return 3; /* 数据读失败（读地址无应答） */
    }
    if (st != 0) {
        return 2; /* D2 段失败 */
    }
    delay_ms(MS5611_CONV_WAIT_MS);

    /* 换算按页面原式（dT 表达式不变——页面 `D2 - (Cal_C1_6[5] * 256.0)`；
     * 页面 dT 声明 uint32_t 低 20℃ 负值回绕、乘数 32 位有符号溢出——本件
     * 取有符号 64 位 long long（标准实现 int64 口径，见上方注释） */
    dT = (long long)(d2 - (ms5611_cal[5] * 256.0));
    temp = 2000 + ((float)dT * ms5611_cal[6]) / 8388608.0;
    off = (long long)(ms5611_cal[2] * 65536.0 + ms5611_cal[4] * dT / 128);
    sens = (long long)(ms5611_cal[1] * 32768.0 + ms5611_cal[3] * dT / 256.0);
    p = (long long)((d1 * sens / 2097152.0 - off) / 32768.0);

    if (temp_c != NULL) {
        /* 温度出参 0.01℃ 分辨率（**页面 Get_TEMP 整数℃截断修正**——
         * dat=(TEMP/1000)*10+(TEMP/100%10) 丢小数，人工复核修正记 notes） */
        *temp_c = (float)temp / 100.0f;
    }
    if (pressure_pa != NULL) {
        /* 气压出参 Pa（**页面 /100 = hPa——P 单位 0.01mbar == 1Pa，统一出
         * Pa 修正**，notes 记录） */
        *pressure_pa = (float)p;
    }
    return 0;
}

float ms5611_read_altitude(float pa)
{
    /* 与 bmp180 共用 44330 海拔公式（bmp180_read_altitude 同式——
     * math.h/pow，ir_distance 先例；两件分工见 manifest notes） */
    return 44330.0f * (1.0f - (float)pow(pa / 101325.0, 1.0 / 5.255));
}
