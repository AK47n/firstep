/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《BH1750光照强度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/bh1750-light-intensity-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "bh1750_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* BH1750 软 I2C 位操作原语（立创 bsp 同款时序：SCL 半周期 5us ≈ 100kHz 级
 * 总线速度，BH1750 规格 ≤400kHz，裕量充足；与 mspm0 版同构——页面原式
 * GPIO_Mode_Out_OD（开漏输出）+ GPIO_Mode_IPU（上拉输入）→ ml_gpio
 * OUT_OD/IU，SDA 方向运行时切换（写 = 输出驱动，读 = 输入采样——总线需
 * 板上/模块自带上拉电阻；页面 GPIO_Init 后 GPIO_SetBits 拉高 = init 时
 * 置两脚高）。 */
#define BH1750_SDA_OUT()  gpio_init(BH1750_SDA_GPIO, BH1750_SDA_PIN, OUT_OD)
#define BH1750_SDA_IN()   gpio_init(BH1750_SDA_GPIO, BH1750_SDA_PIN, IU)
#define BH1750_SDA_GET()  gpio_get(BH1750_SDA_GPIO, BH1750_SDA_PIN)
#define BH1750_SDA(x)     gpio_set(BH1750_SDA_GPIO, BH1750_SDA_PIN, (x))
#define BH1750_SCL(x)     gpio_set(BH1750_SCL_GPIO, BH1750_SCL_PIN, (x))

#define BH1750_ADDR_WRITE 0x46 /* 器件地址 0x23<<1（ALT ADDRESS 接地；接电源
                                * 时地址 0xB8，改此处即可） */
#define BH1750_CMD_POWER_ON 0x01
#define BH1750_CMD_CONT_H_RES 0x10 /* 连续高分辨率：1 lx 分辨率，测量 ≥120ms */

static void bh1750_iic_start(void)
{
    BH1750_SDA_OUT();
    BH1750_SDA(1);
    delay_us(5);
    BH1750_SCL(1);
    delay_us(5);
    BH1750_SDA(0);
    delay_us(5);
    BH1750_SCL(0);
    delay_us(5);
}

static void bh1750_iic_stop(void)
{
    BH1750_SDA_OUT();
    BH1750_SCL(0);
    BH1750_SDA(0);
    BH1750_SCL(1);
    delay_us(5);
    BH1750_SDA(1);
    delay_us(5);
}

/* ack 后置一位应答/非应答：is_nack = 0 应答（继续收下一字节）、1 = 非应答
 * （最后一字节，通知从机停发） */
static void bh1750_iic_send_ack(uint8_t is_nack)
{
    BH1750_SDA_OUT();
    BH1750_SCL(0);
    BH1750_SDA(0);
    delay_us(5);
    if (is_nack) {
        BH1750_SDA(1);
    } else {
        BH1750_SDA(0);
    }
    BH1750_SCL(1);
    delay_us(5);
    BH1750_SCL(0);
    BH1750_SDA(1);
}

static uint8_t bh1750_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    BH1750_SCL(0);
    BH1750_SDA(1);
    BH1750_SDA_IN();
    delay_us(5);
    BH1750_SCL(1);
    delay_us(5);
    while ((BH1750_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        bh1750_iic_stop();
        return 1; /* 超时无应答 */
    }
    BH1750_SCL(0);
    BH1750_SDA_OUT();
    return 0;
}

static void bh1750_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    BH1750_SDA_OUT();
    BH1750_SCL(0);
    for (i = 0; i < 8; i++) {
        BH1750_SDA((dat & 0x80) >> 7);
        delay_us(1);
        BH1750_SCL(1);
        delay_us(5);
        BH1750_SCL(0);
        delay_us(5);
        dat <<= 1;
    }
}

static uint8_t bh1750_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    BH1750_SDA_IN();
    for (i = 0; i < 8; i++) {
        BH1750_SCL(0);
        delay_us(5);
        BH1750_SCL(1);
        delay_us(5);
        receive <<= 1;
        if (BH1750_SDA_GET()) {
            receive |= 1;
        }
        delay_us(5);
    }
    BH1750_SCL(0);
    return receive;
}

/* 写一字节命令：起始 → 地址+写（0x46）→ 命令 → 应答 → 停止；返回 0=成功、
 * 1=无应答。页面 Single_Write_BH1750 返回 0/1/2（器件地址错/命令错——两处
 * 应答检查），本实现统一 0/1（mspm0 版同款：差异无碍——两个失败位语义相同，
 * 收敛为一个「无应答」状态码）。 */
static uint8_t bh1750_write_cmd(uint8_t cmd)
{
    bh1750_iic_start();
    bh1750_iic_send_byte(BH1750_ADDR_WRITE);
    if (bh1750_iic_wait_ack() != 0) {
        return 1;
    }
    bh1750_iic_send_byte(cmd);
    if (bh1750_iic_wait_ack() != 0) {
        return 1;
    }
    bh1750_iic_stop();
    return 0;
}

void bh1750_init(void)
{
    /* 上电（掉电模式 → 等待测量命令）；页面 GY30_Init 的 GPIO 初始化由
     * 本模块 init 内 gpio_init 完成（页面原式：OD + 两脚置高 = 总线空闲
     * 电平——页面 GPIO_SetBits 拉高） */
    gpio_init(BH1750_SCL_GPIO, BH1750_SCL_PIN, OUT_OD);
    gpio_init(BH1750_SDA_GPIO, BH1750_SDA_PIN, OUT_OD);
    gpio_set(BH1750_SCL_GPIO, BH1750_SCL_PIN, 1);
    gpio_set(BH1750_SDA_GPIO, BH1750_SDA_PIN, 1);
    (void)bh1750_write_cmd(BH1750_CMD_POWER_ON);
}

uint8_t bh1750_start_measure(void)
{
    return bh1750_write_cmd(BH1750_CMD_CONT_H_RES);
}

uint8_t bh1750_read_lux(float *lux)
{
    uint8_t dat_hi;
    uint8_t dat_lo;
    uint16_t raw;

    bh1750_iic_start();
    bh1750_iic_send_byte(BH1750_ADDR_WRITE + 1); /* 地址 + 读（0x47） */
    if (bh1750_iic_wait_ack() != 0) {
        return 1; /* 页面缺陷①修正：读路径应答不检查 → 返回 1 */
    }
    dat_hi = bh1750_iic_read_byte();
    bh1750_iic_send_ack(0); /* 应答 */
    dat_lo = bh1750_iic_read_byte();
    bh1750_iic_send_ack(1); /* 非应答（最后一字节） */
    bh1750_iic_stop();

    raw = ((uint16_t)dat_hi << 8) | dat_lo;
    if (lux != 0) {
        *lux = (float)raw / 1.2f; /* 1 lx 分辨率：读数 /1.2 */
    }
    return 0;
}
