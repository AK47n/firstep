/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AHT10温湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/aht10-temp-humi-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "aht10_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* AHT10 软 I2C 位操作原语（立创 bsp 同款时序：SCL 半周期 2-4us ≈ 100kHz 级
 * 总线速度，AHT10 规格 ≤400kHz，裕量充足；与 mspm0 版同构——页面原式
 * GPIO_Mode_Out_OD（开漏输出）+ GPIO_Mode_IPU（上拉输入）→ ml_gpio
 * OUT_OD/IU，SDA 方向运行时切换（写 = 输出驱动，读 = 输入采样——总线需
 * 板上/模块自带上拉电阻）。 */
#define AHT10_SDA_OUT()  gpio_init(AHT10_SDA_GPIO, AHT10_SDA_PIN, OUT_OD)
#define AHT10_SDA_IN()   gpio_init(AHT10_SDA_GPIO, AHT10_SDA_PIN, IU)
#define AHT10_SDA_GET()  gpio_get(AHT10_SDA_GPIO, AHT10_SDA_PIN)
#define AHT10_SDA(x)     gpio_set(AHT10_SDA_GPIO, AHT10_SDA_PIN, (x))
#define AHT10_SCL(x)     gpio_set(AHT10_SCL_GPIO, AHT10_SCL_PIN, (x))

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

/* ack = 0 应答 / 1 非应答（页面 IIC_Send_Ack 原式：先置 0 再按 ack 重设——
 * ack=0 时同值二次写，保留原式） */
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

/* 等待从机应答（页面 I2C_WaitAck：0=有应答/1=超时无应答；超时发停止信号）。
 * 页面 `char ack` 冗余变量已收敛（成功路径语义 = 有应答返回 0）。 */
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

    /* 等采集完成：重发读地址直到有应答（最多 5 次 ×1ms；页面循环后不判
     * 超时——缺陷③修正：超时返回 1，不再继续读垃圾数据）
     * ⚠️ 已知规格偏差（页面/mspm0 同款）：窗口 ~25ms ≪ AHT10 手册测量
     * ≥80ms——按页面原式保留（器件测完前 NACK 读地址、ACK 即数据就绪，
     * 真机如失败调大读前延时即可，单点调参——mspm0 侧 notes 同记录）。 */
    delay_ms(20);
    for (timeout = 0; timeout < 5; timeout++) {
        delay_ms(1);
        aht10_iic_start();
        aht10_iic_send_byte(0x38 << 1 | 1); /* 器件地址 + 读（页面注释
                                             * 「写命令」系笔误——缺陷④） */
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
    if (humidity_rh != 0) {
        *humidity_rh = (float)dat / 1048576.0f * 100.0f;
    }
    dat = ((uint32_t)(buff[3] & 0x0F) << 16) | ((uint32_t)buff[4] << 8) | buff[5];
    if (temperature_c != 0) {
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
