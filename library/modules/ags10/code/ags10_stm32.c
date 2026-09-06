/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AGS10有害气体传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ags10-harmful-gas-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ags10_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* AGS10 软 I2C 位操作原语（立创 bsp 同款时序：半周期 5us ≈ 100kHz 级。
 * ⚠️ 页面规格表注明 I2C 接口速率 ≤15kHz 与页面代码时序不一致——按页面
 * 代码实现，真机通信异常时按规格调慢 SCL 半周期延时即可（唯一时序宏点——
 * mspm0 侧 notes 同记录，缺陷④）。页面 delay_1us(5)/delay_1ms(1) 本库
 * 不存在 → delay_us(5)/delay_ms(1)（缺陷③改写）。
 * SDA 方向切换：写 = 输出（SDA_OUT + 电平），读 = 输入（SDA_IN + 采样）；
 * 页面原式 GPIO_Mode_Out_OD（开漏输出）+ GPIO_Mode_IPU（上拉输入）→
 * ml_gpio OUT_OD/IU——总线需 1kΩ～10kΩ 上拉（页面正文）。 */
#define AGS10_SDA_OUT()  gpio_init(AGS10_SDA_GPIO, AGS10_SDA_PIN, OUT_OD)
#define AGS10_SDA_IN()   gpio_init(AGS10_SDA_GPIO, AGS10_SDA_PIN, IU)
#define AGS10_SDA_GET()  gpio_get(AGS10_SDA_GPIO, AGS10_SDA_PIN)
#define AGS10_SDA(x)     gpio_set(AGS10_SDA_GPIO, AGS10_SDA_PIN, (x))
#define AGS10_SCL(x)     gpio_set(AGS10_SCL_GPIO, AGS10_SCL_PIN, (x))

static void ags10_iic_start(void)
{
    AGS10_SDA_OUT();
    AGS10_SDA(1);
    AGS10_SCL(1);
    delay_us(5);
    AGS10_SDA(0);
    delay_us(5);
    AGS10_SCL(0);
    delay_us(5);
}

static void ags10_iic_stop(void)
{
    AGS10_SDA_OUT();
    AGS10_SCL(0);
    AGS10_SDA(0);
    AGS10_SCL(1);
    delay_us(5);
    AGS10_SDA(1);
    delay_us(5);
}

static void ags10_iic_send_nack(void)
{
    /* 页面 Send_Nack 原式：SDA(0) 打底再置 1（冗余二次写，末值 = 高电平 =
     * 非应答），照页面保留（缺陷⑦） */
    AGS10_SDA_OUT();
    AGS10_SCL(0);
    AGS10_SDA(0);
    AGS10_SDA(1);
    AGS10_SCL(1);
    delay_us(5);
    AGS10_SCL(0);
    AGS10_SDA(0);
}

static void ags10_iic_send_ack(void)
{
    /* 页面 Send_Ack 原式：SDA(1) 打底再置 0（冗余二次写，末值 = 低电平 =
     * 应答），照页面保留（缺陷⑦） */
    AGS10_SDA_OUT();
    AGS10_SCL(0);
    AGS10_SDA(1);
    AGS10_SDA(0);
    AGS10_SCL(1);
    delay_us(5);
    AGS10_SCL(0);
    AGS10_SDA(1);
}

static uint8_t ags10_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    AGS10_SCL(0);
    AGS10_SDA(1);
    AGS10_SDA_IN();
    delay_us(5);
    AGS10_SCL(1);
    delay_us(5);
    while ((AGS10_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        ags10_iic_stop();
        return 1; /* 非应答/超时（页面 1=非应答 0=应答） */
    }
    AGS10_SCL(0);
    AGS10_SDA_OUT();
    return 0;
}

static void ags10_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    AGS10_SDA_OUT();
    AGS10_SCL(0);
    for (i = 0; i < 8; i++) {
        AGS10_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        AGS10_SCL(1);
        delay_us(5);
        AGS10_SCL(0);
        delay_us(5);
        dat <<= 1;
    }
}

static uint8_t ags10_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    AGS10_SDA_IN();
    for (i = 0; i < 8; i++) {
        AGS10_SCL(0);
        delay_us(5);
        AGS10_SCL(1);
        delay_us(5);
        receive <<= 1;
        if (AGS10_SDA_GET()) {
            receive |= 1;
        }
    }
    AGS10_SCL(0);
    return receive;
}

/* CRC8（页面 Calc_CRC8 原式，自包含）：初值 0xFF、多项式 0x31
 * （x8 + x5 + x4 +1）——每个数据字节逐位
 * (crc & 0x80) ? (crc<<1)^POLYNOMIAL : (crc<<1)。页面非 static 通用名 →
 * 静态化。 */
static uint8_t ags10_crc8(const uint8_t *dat, uint8_t num)
{
    uint8_t i;
    uint8_t byte;
    uint8_t crc = 0xFFu;

    for (byte = 0; byte < num; byte++) {
        crc ^= dat[byte];
        for (i = 0; i < 8; i++) {
            if (crc & 0x80u) {
                crc = (uint8_t)((crc << 1) ^ 0x31u);
            } else {
                crc = (uint8_t)(crc << 1);
            }
        }
    }
    return crc;
}

void ags10_init(void)
{
    /* AGS10 无独立初始化序列（页面演示上电直接读；模块预热 ≥120s 期间
     * 读数起步属器件特性，等待归调用方——mlx90614/at24c02 空实现先例）；
     * 引脚配置 = 页面 ags10_gpio_init 原式（OD + 两脚置高 = 总线空闲电平，
     * 页面 GPIO_SetBits 拉高——「SCL上电必须保持高电平」要求） */
    gpio_init(AGS10_SCL_GPIO, AGS10_SCL_PIN, OUT_OD);
    gpio_init(AGS10_SDA_GPIO, AGS10_SDA_PIN, OUT_OD);
    gpio_set(AGS10_SCL_GPIO, AGS10_SCL_PIN, 1);
    gpio_set(AGS10_SDA_GPIO, AGS10_SDA_PIN, 1);
}

uint8_t ags10_read(uint32_t *voc_ppb)
{
    uint8_t timeout = 0;
    uint8_t data[5] = {0};

    /* 写寄存器 0x00（页面原式：地址 0x34 + 寄存器值——错误码 1/2 页面语义） */
    ags10_iic_start();
    ags10_iic_send_byte((uint8_t)((AGS10_ADDR << 1) | 0u)); /* 写 0x34 */
    if (ags10_iic_wait_ack() == 1) {
        return 1; /* 通信失败 */
    }
    ags10_iic_send_byte(AGS10_REG_TVOC);
    if (ags10_iic_wait_ack() == 1) {
        return 2; /* 发送失败 */
    }
    ags10_iic_stop();

    /* 读地址应答重试（页面函数注释：≤50×1ms；⚠️ 页面实现比较方向写反——
     * `while((WaitAck()==1) && (timeout >= 50))` 循环一次即退、超时分支永不
     * 触发——本实现按注释语义修正为 timeout < AGS10_RETRY_MAX，上游缺陷
     * 记录，ir_remote/nrf24l01 先例） */
    do {
        delay_ms(1);
        timeout++;
        ags10_iic_start();
        ags10_iic_send_byte((uint8_t)((AGS10_ADDR << 1) | 1u)); /* 读 0x35 */
    } while ((ags10_iic_wait_ack() == 1) && (timeout < AGS10_RETRY_MAX));
    if (timeout >= AGS10_RETRY_MAX) {
        return 3; /* 等待超时 */
    }

    /* 5 字节回包：状态 + TVOC 24bit（data[1..3]）+ CRC（data[4]，最后一字节
     * 非应答——页面原式；状态字 data[0] 页面未说明语义，读入不检查） */
    data[0] = ags10_iic_read_byte();
    ags10_iic_send_ack();
    data[1] = ags10_iic_read_byte();
    ags10_iic_send_ack();
    data[2] = ags10_iic_read_byte();
    ags10_iic_send_ack();
    data[3] = ags10_iic_read_byte();
    ags10_iic_send_ack();
    data[4] = ags10_iic_read_byte();
    ags10_iic_send_nack();
    ags10_iic_stop();

    if (ags10_crc8(data, 4) != data[4]) {
        return 4; /* 校验失败（页面失败码 4；页面注释掉的 printf 不落） */
    }
    if (voc_ppb != 0) {
        *voc_ppb = ((uint32_t)data[1] << 16) | ((uint32_t)data[2] << 8) | data[3];
    }
    return 0;
}
