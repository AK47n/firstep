/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《SGP30气体传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/sgp30-gas-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "sgp30.h"
#include "delay.h" /* delay_us / delay_ms：软 I2C 位操作与测量延时 */
#include "ti_msp_dl_config.h" /* SGP30_SCL_PORT/PIN、SGP30_SDA_PORT/PIN、
                                * SGP30_SCL_IOMUX / SGP30_SDA_IOMUX
                                * （SysConfig 生成命名：<实例>_<引脚名>_PORT/
                                * PIN/_IOMUX——SCL/SDA 跨 GPIOA/GPIOB 两端口，
                                * 生成器按引脚名分派各口宏，无组合 SGP30_PORT；
                                * 编译矩阵实测，照 max7219 先例） */

/* SGP30 软 I2C 位操作原语（立创 bsp 同款时序：SCL 半周期 5us ≈ 100kHz 级
 * 总线速度，SGP30 规格 ≤400kHz，裕量充足；页面原值）。
 * SDA 方向切换：写 = 输出（SDA_OUT + 电平），读 = 输入（SDA_IN + 采样）。 */

#define SGP30_SDA_OUT()                                        \
    do {                                                       \
        DL_GPIO_initDigitalOutput(SGP30_SDA_IOMUX);            \
        DL_GPIO_setPins(SGP30_SDA_PORT, SGP30_SDA_PIN);        \
        DL_GPIO_enableOutput(SGP30_SDA_PORT, SGP30_SDA_PIN);   \
    } while (0)

#define SGP30_SDA_IN()                          \
    do {                                        \
        DL_GPIO_initDigitalInput(SGP30_SDA_IOMUX); \
    } while (0)

#define SGP30_SDA_GET() \
    ((DL_GPIO_readPins(SGP30_SDA_PORT, SGP30_SDA_PIN) & SGP30_SDA_PIN) ? 1 : 0)

#define SGP30_SDA(x)                                                 \
    do {                                                             \
        if (x) {                                                     \
            DL_GPIO_setPins(SGP30_SDA_PORT, SGP30_SDA_PIN);          \
        } else {                                                     \
            DL_GPIO_clearPins(SGP30_SDA_PORT, SGP30_SDA_PIN);        \
        }                                                            \
    } while (0)

#define SGP30_SCL(x)                                                 \
    do {                                                             \
        if (x) {                                                     \
            DL_GPIO_setPins(SGP30_SCL_PORT, SGP30_SCL_PIN);          \
        } else {                                                     \
            DL_GPIO_clearPins(SGP30_SCL_PORT, SGP30_SCL_PIN);        \
        }                                                            \
    } while (0)

static void sgp30_iic_start(void)
{
    SGP30_SDA_OUT();
    SGP30_SCL(0);
    delay_us(1);
    SGP30_SDA(1);
    SGP30_SCL(1);
    delay_us(5);
    SGP30_SDA(0);
    delay_us(5);
    SGP30_SCL(0);
    delay_us(5);
}

static void sgp30_iic_stop(void)
{
    SGP30_SDA_OUT();
    SGP30_SCL(0);
    SGP30_SDA(0);
    SGP30_SCL(1);
    delay_us(5);
    SGP30_SDA(1);
    delay_us(5);
}

static void sgp30_iic_send_ack(uint8_t ack)
{
    /* 参数 0=发送应答、1=发送非应答（页面 IIC_Send_Ack 语义——0/1 与直觉
     * 相反，命名照页面保留）；SDA(0) 打底再按 ack 重设 = 页面原式冗余写 */
    SGP30_SDA_OUT();
    SGP30_SCL(0);
    SGP30_SDA(0);
    delay_us(5);
    if (!ack) {
        SGP30_SDA(0);
    } else {
        SGP30_SDA(1);
    }
    SGP30_SCL(1);
    delay_us(5);
    SGP30_SCL(0);
    SGP30_SDA(1);
}

static uint8_t sgp30_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    SGP30_SCL(0);
    SGP30_SDA(1);
    SGP30_SDA_IN();
    delay_us(5);
    SGP30_SCL(1);
    delay_us(5);
    while ((SGP30_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        sgp30_iic_stop();
        return 1; /* 超时无应答 */
    }
    SGP30_SCL(0);
    SGP30_SDA_OUT();
    return 0;
}

static void sgp30_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    SGP30_SDA_OUT();
    SGP30_SCL(0);
    for (i = 0; i < 8; i++) {
        SGP30_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        SGP30_SCL(1);
        delay_us(5);
        SGP30_SCL(0);
        delay_us(5);
        dat <<= 1;
    }
}

static uint8_t sgp30_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    SGP30_SDA_IN();
    for (i = 0; i < 8; i++) {
        SGP30_SCL(0);
        delay_us(5);
        SGP30_SCL(1);
        delay_us(5);
        receive <<= 1;
        if (SGP30_SDA_GET()) {
            receive |= 1;
        }
        delay_us(5);
    }
    SGP30_SCL(0);
    return receive;
}

/* CRC8（SGP30 数据手册：多项式 0x31、初值 0xFF——同 SHT30/AGS10 系）：
 * 每个数据字节逐位 (crc & 0x80) ? (crc<<1)^POLYNOMIAL : (crc<<1)。
 * 页面实现读回 CRC 后即弃（`crc = crc`），本实现按器件规范校验。 */
static uint8_t sgp30_crc8(const uint8_t *data, int len)
{
    const uint8_t polynomial = 0x31u;
    uint8_t crc = 0xFFu;
    int j;
    int i;

    for (j = 0; j < len; j++) {
        crc ^= *data++;
        for (i = 0; i < 8; i++) {
            crc = (crc & 0x80u) ? (uint8_t)((crc << 1) ^ polynomial)
                                : (uint8_t)(crc << 1);
        }
    }
    return crc;
}

/* 写命令（页面 SGP30_Write_cmd 语义）：START + 写地址 + 2 字节命令 + STOP +
 * delay_ms(100)（页面内嵌延时——覆盖器件测量时长/命令处理）。
 * 返回 0 = 成功；1/2/3 = 地址/命令字节应答失败（页面原式不查应答，
 * 按 sht30 风格补）。 */
static uint8_t sgp30_write_cmd(uint16_t cmd)
{
    sgp30_iic_start();
    sgp30_iic_send_byte((uint8_t)((SGP30_ADDR << 1) | 0u)); /* 写 0xB0 */
    if (sgp30_iic_wait_ack() == 1) {
        return 1;
    }
    sgp30_iic_send_byte((uint8_t)(cmd >> 8));
    if (sgp30_iic_wait_ack() == 1) {
        return 2;
    }
    sgp30_iic_send_byte((uint8_t)(cmd & 0xFFu));
    if (sgp30_iic_wait_ack() == 1) {
        return 3;
    }
    sgp30_iic_stop();
    delay_ms(100);
    return 0;
}

void sgp30_init(void)
{
    (void)sgp30_write_cmd(SGP30_CMD_INIT_AIR); /* 初始化空气特征值/基准（页面
                                                * SGP30_Init 语义：0x2003） */
}

uint8_t sgp30_read(uint16_t *tvoc_ppb, uint16_t *co2_ppm)
{
    uint8_t buff[6] = {0};
    uint8_t ret;

    /* 发测量命令（0x2008——页面演示每次读前重发；内嵌延时覆盖测量时长） */
    ret = sgp30_write_cmd(SGP30_CMD_MEASURE_AIR);
    if (ret != 0) {
        return ret;
    }

    /* 读回包：地址 0xB1（读） */
    sgp30_iic_start();
    sgp30_iic_send_byte((uint8_t)((SGP30_ADDR << 1) | 1u));
    if (sgp30_iic_wait_ack() == 1) {
        return 4; /* 读地址应答失败（页面无重试、直接失败） */
    }

    /* 6 字节回包：CO2 高/低 + CRC + TVOC 高/低 + CRC（页面只读 5 字节漏 TVOC
     * CRC 字节——数据手册回包 6 字节，器件正确性修正：读满 6 字节+两组校验） */
    buff[0] = sgp30_iic_read_byte();
    sgp30_iic_send_ack(0);
    buff[1] = sgp30_iic_read_byte();
    sgp30_iic_send_ack(0);
    buff[2] = sgp30_iic_read_byte();
    sgp30_iic_send_ack(0);
    buff[3] = sgp30_iic_read_byte();
    sgp30_iic_send_ack(0);
    buff[4] = sgp30_iic_read_byte();
    sgp30_iic_send_ack(0);
    buff[5] = sgp30_iic_read_byte();
    sgp30_iic_send_ack(1);
    sgp30_iic_stop();

    /* CRC8 两组校验（器件正确性修正——页面缺校验，ir_remote 反码校验先例） */
    if ((sgp30_crc8(buff, 2) != buff[2]) || (sgp30_crc8(buff + 3, 2) != buff[5])) {
        return 5; /* CRC 校验失败 */
    }

    if (co2_ppm != NULL) {
        *co2_ppm = (uint16_t)(((uint16_t)buff[0] << 8) | buff[1]);
    }
    if (tvoc_ppb != NULL) {
        *tvoc_ppb = (uint16_t)(((uint16_t)buff[3] << 8) | buff[4]);
    }
    return 0;
}
