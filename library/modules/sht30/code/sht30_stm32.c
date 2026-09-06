/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《SHT30温湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/sht30-temp-humi-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "sht30_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* SHT30 软 I2C 位操作原语（立创 bsp 同款时序：SCL 半周期 5us ≈ 100kHz 级
 * 总线速度，SHT30 规格 ≤400kHz，裕量充足）。
 * ⚠️ 页面电平配置 = 全批唯一一派：**GPIO_Mode_Out_PP（推挽输出）+
 * GPIO_Mode_IN_FLOATING（浮空输入）**（其余 5 页为 OD+IPU）——工作前提 =
 * 模块自带 1k-10k 上拉电阻（页面正文「I2C 物理接口 1kΩ～10kΩ 上拉」系
 * AGS10 页同构描述，SHT30 模块板上自带）；SDA 方向切换：写 = 输出驱动，
 * 读 = 输入采样。 */
#define SHT30_SDA_OUT()  gpio_init(SHT30_SDA_GPIO, SHT30_SDA_PIN, OUT_PP)
#define SHT30_SDA_IN()   gpio_init(SHT30_SDA_GPIO, SHT30_SDA_PIN, IF)
#define SHT30_SDA_GET()  gpio_get(SHT30_SDA_GPIO, SHT30_SDA_PIN)
#define SHT30_SDA(x)     gpio_set(SHT30_SDA_GPIO, SHT30_SDA_PIN, (x))
#define SHT30_SCL(x)     gpio_set(SHT30_SCL_GPIO, SHT30_SCL_PIN, (x))

static void sht30_iic_start(void)
{
    SHT30_SDA_OUT();
    SHT30_SCL(1);
    SHT30_SDA(0);
    SHT30_SDA(1); /* 页面原式：SCL 高期间先 SDA 低再 SDA 高（Stop 边沿）——
                    * 含多余边沿，最终态正确（缺陷⑥记录，按页面原样保留） */
    delay_us(5);
    SHT30_SDA(0);
    delay_us(5);
    SHT30_SCL(0);
}

static void sht30_iic_stop(void)
{
    SHT30_SDA_OUT();
    SHT30_SCL(0);
    SHT30_SDA(0);
    SHT30_SCL(1);
    delay_us(5);
    SHT30_SDA(1);
    delay_us(5);
}

static void sht30_iic_send_ack(uint8_t is_nack)
{
    SHT30_SDA_OUT();
    SHT30_SCL(0);
    SHT30_SDA(0); /* 页面原式：先置 0，再按 is_nack 重设（is_nack=0 时同值二次写） */
    delay_us(5);
    if (!is_nack) {
        SHT30_SDA(0);
    } else {
        SHT30_SDA(1);
    }
    SHT30_SCL(1);
    delay_us(5);
    SHT30_SCL(0);
    SHT30_SDA(1);
}

/* 等待从机应答（页面 I2C_WaitAck：0=有应答/1=超时无应答；超时发停止信号）。
 * 页面 `char ack` 死变量已收敛（缺陷⑤）。 */
static uint8_t sht30_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    SHT30_SCL(0);
    SHT30_SDA(1);
    SHT30_SDA_IN();
    SHT30_SCL(1);
    while ((SHT30_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        sht30_iic_stop();
        return 1; /* 超时无应答 */
    }
    SHT30_SCL(0);
    SHT30_SDA_OUT();
    return 0;
}

static void sht30_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    SHT30_SDA_OUT();
    SHT30_SCL(0);
    for (i = 0; i < 8; i++) {
        SHT30_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        SHT30_SCL(1);
        delay_us(5);
        SHT30_SCL(0);
        delay_us(5);
        dat <<= 1;
    }
}

static uint8_t sht30_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    SHT30_SDA_IN();
    for (i = 0; i < 8; i++) {
        SHT30_SCL(0);
        delay_us(5);
        SHT30_SCL(1);
        delay_us(5);
        receive <<= 1;
        if (SHT30_SDA_GET()) {
            receive |= 1;
        }
        delay_us(5);
    }
    SHT30_SCL(0);
    return receive;
}

/* CRC8（立创页面原式）：多项式 0x31、初值 0xFF——每个数据字节逐位
 * (crc & 0x80) ? (crc<<1)^POLYNOMIAL : (crc<<1)。页面 crc8 为通用名 +
 * 非 static（缺陷④）→ 静态化。 */
static uint8_t sht30_crc8(const uint8_t *data, int len)
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

/* 写测量模式/命令（页面 SHT31_Write_mode）：START + 写地址 + 2 字节命令；
 * 返回 0 = 成功、1/2/3 = 应答失败（页面失败码）。页面把 IIC_Stop 注释掉
 * （跟手重发 START = 重复起始），按页面原样不补 STOP（缺陷⑥注释）。 */
static uint8_t sht30_write_mode(uint16_t dat)
{
    sht30_iic_start();
    sht30_iic_send_byte((uint8_t)((SHT30_ADDR << 1) | 0u));
    if (sht30_iic_wait_ack() == 1) {
        return 1;
    }
    sht30_iic_send_byte((uint8_t)(dat >> 8));
    if (sht30_iic_wait_ack() == 1) {
        return 2;
    }
    sht30_iic_send_byte((uint8_t)(dat & 0xFFu));
    if (sht30_iic_wait_ack() == 1) {
        return 3;
    }
    return 0;
}

void sht30_init(void)
{
    /* 引脚配置：SCL 按批次 3/01 回修口径统一为开漏输出 + 置高（F1 复位后
     * 浮空输入、ODR 写入无效——总线空闲电平必须显式置高；页面原式为推挽
     * 输出无 SetBits，差异记录 notes）；SDA 保持页面原式推挽+浮空（全批
     * 唯一一派，工作前提 = 模块自带 1k-10k 上拉）。随后周期模式命令 */
    gpio_init(SHT30_SCL_GPIO, SHT30_SCL_PIN, OUT_OD);
    gpio_init(SHT30_SDA_GPIO, SHT30_SDA_PIN, OUT_PP);
    gpio_set(SHT30_SCL_GPIO, SHT30_SCL_PIN, 1);
    (void)sht30_write_mode(SHT30_CMD_PERIODIC); /* 周期模式：每秒 1 次高重复 */
}

uint8_t sht30_read(float *temperature_c, float *humidity_rh)
{
    uint8_t buff[6] = {0};
    uint16_t i = 0;
    uint16_t data_16 = 0;

    /* 周期模式命令（页面每次读前重发；0x2130 = 每秒 1 次高重复测量） */
    (void)sht30_write_mode(SHT30_CMD_PERIODIC);

    /* 发读命令（0xE000：周期模式读） */
    sht30_iic_start();
    sht30_iic_send_byte((uint8_t)((SHT30_ADDR << 1) | 0u));
    if (sht30_iic_wait_ack() == 1) {
        return 1;
    }
    sht30_iic_send_byte((uint8_t)(SHT30_CMD_READ >> 8));
    if (sht30_iic_wait_ack() == 1) {
        return 2;
    }
    sht30_iic_send_byte((uint8_t)(SHT30_CMD_READ & 0xFFu));
    if (sht30_iic_wait_ack() == 1) {
        return 3;
    }

    /* 等测量完成：重发读地址直到有应答（页面 ≤20×2ms 超时） */
    do {
        i++;
        if (i > SHT30_READ_RETRY_MAX) {
            return 4;
        }
        delay_ms(SHT30_READ_RETRY_MS);
        sht30_iic_start();
        sht30_iic_send_byte((uint8_t)((SHT30_ADDR << 1) | 1u)); /* 读 */
    } while (sht30_iic_wait_ack() == 1);

    /* 6 字节回包：温度高/低 + CRC + 湿度高/低 + CRC（最后一字节非应答） */
    buff[0] = sht30_iic_read_byte();
    sht30_iic_send_ack(0);
    buff[1] = sht30_iic_read_byte();
    sht30_iic_send_ack(0);
    buff[2] = sht30_iic_read_byte();
    sht30_iic_send_ack(0);
    buff[3] = sht30_iic_read_byte();
    sht30_iic_send_ack(0);
    buff[4] = sht30_iic_read_byte();
    sht30_iic_send_ack(0);
    buff[5] = sht30_iic_read_byte();
    sht30_iic_send_ack(1);
    sht30_iic_stop();

    /* CRC8 两组校验（页面原式；失败返回 5——页面校验失败 printf 已剔除） */
    if ((sht30_crc8(buff, 2) == buff[2]) && (sht30_crc8(buff + 3, 2) == buff[5])) {
        /* 温度：data/65535×175−45（页面 0.01 系数）；湿度：data/65535×100 */
        data_16 = (uint16_t)(((uint16_t)buff[0] << 8) | buff[1]);
        if (temperature_c != 0) {
            *temperature_c = (float)data_16 / 65535.0f * 175.0f - 45.0f;
        }
        data_16 = (uint16_t)(((uint16_t)buff[3] << 8) | buff[4]);
        if (humidity_rh != 0) {
            *humidity_rh = (float)data_16 / 65535.0f * 100.0f;
        }
        return 0;
    }
    return 5; /* CRC 校验失败（页面失败码） */
}

uint8_t sht30_read_temperature(float *temperature_c)
{
    float t = 0.0f;
    float h = 0.0f;
    uint8_t ret = sht30_read(&t, &h);
    if ((ret == 0) && (temperature_c != 0)) {
        *temperature_c = t;
    }
    return ret;
}

uint8_t sht30_read_humidity(float *humidity_rh)
{
    float t = 0.0f;
    float h = 0.0f;
    uint8_t ret = sht30_read(&t, &h);
    if ((ret == 0) && (humidity_rh != 0)) {
        *humidity_rh = h;
    }
    return ret;
}
