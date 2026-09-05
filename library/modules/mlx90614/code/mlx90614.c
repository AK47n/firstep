#include "mlx90614.h"
#include "delay.h" /* delay_us：软 I2C 位操作延时 */
#include "ti_msp_dl_config.h" /* MLX90614_PORT / MLX90614_SCL_PIN /
                               * MLX90614_SDA_PIN / MLX90614_SCL_IOMUX /
                               * MLX90614_SDA_IOMUX
                               * （SysConfig 生成命名：<实例>_<引脚名>_IOMUX，
                               * 编译矩阵实测；照 AHT10_SCL_IOMUX 先例） */

/* MLX90614 软 I2C（SMBus 兼容）位操作原语（立创 bsp 同款时序，照 aht10 先例：
 * SCL 半周期 2us → 标称 ≈250kHz（含软件开销实际略低），高于 SMBus 100kHz
 * 规约但 SMBus 无硬件抓错、页面原时序 1us 更超且演示可通——真机验证留后续；
 * 如遇长线/干扰可按注释将各 delay_us(2) 提至 5us 降速。SDA 方向切换：写 =
 * 输出（SDA_OUT + 电平），读 = 输入（SDA_IN + 采样）。 */

#define MLX90614_SDA_OUT()                                 \
    do {                                                   \
        DL_GPIO_initDigitalOutput(MLX90614_SDA_IOMUX);     \
        DL_GPIO_setPins(MLX90614_PORT, MLX90614_SDA_PIN);  \
        DL_GPIO_enableOutput(MLX90614_PORT, MLX90614_SDA_PIN); \
    } while (0)

#define MLX90614_SDA_IN()                          \
    do {                                           \
        DL_GPIO_initDigitalInput(MLX90614_SDA_IOMUX); \
    } while (0)

#define MLX90614_SDA_GET() \
    ((DL_GPIO_readPins(MLX90614_PORT, MLX90614_SDA_PIN) & MLX90614_SDA_PIN) ? 1 : 0)

#define MLX90614_SDA(level)                                    \
    do {                                                       \
        if (level) {                                           \
            DL_GPIO_setPins(MLX90614_PORT, MLX90614_SDA_PIN);  \
        } else {                                               \
            DL_GPIO_clearPins(MLX90614_PORT, MLX90614_SDA_PIN); \
        }                                                      \
    } while (0)

#define MLX90614_SCL(level)                                    \
    do {                                                       \
        if (level) {                                           \
            DL_GPIO_setPins(MLX90614_PORT, MLX90614_SCL_PIN);  \
        } else {                                               \
            DL_GPIO_clearPins(MLX90614_PORT, MLX90614_SCL_PIN); \
        }                                                      \
    } while (0)

static void mlx90614_iic_start(void)
{
    MLX90614_SDA_OUT();
    MLX90614_SDA(1);
    MLX90614_SCL(1);
    delay_us(2);
    MLX90614_SDA(0);
    delay_us(2);
    MLX90614_SCL(0);
}

static void mlx90614_iic_stop(void)
{
    MLX90614_SDA_OUT();
    MLX90614_SCL(0);
    MLX90614_SDA(0);
    delay_us(2);
    MLX90614_SCL(1);
    MLX90614_SDA(1);
    delay_us(2);
}

/* ack 后置一位应答/非应答：is_nack = 0 应答（继续收下一字节）、1 = 非应答
 * （最后一字节，通知从机停发） */
static void mlx90614_iic_send_ack(uint8_t is_nack)
{
    MLX90614_SDA_OUT();
    MLX90614_SCL(0);
    if (is_nack) {
        MLX90614_SDA(1);
    } else {
        MLX90614_SDA(0);
    }
    delay_us(2);
    MLX90614_SCL(1);
    delay_us(2);
    MLX90614_SCL(0);
    MLX90614_SDA(1);
}

static uint8_t mlx90614_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;
    MLX90614_SDA(1);
    delay_us(1);
    MLX90614_SCL(1);
    delay_us(1);
    MLX90614_SDA_IN();
    delay_us(2);
    while ((MLX90614_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(3);
    }
    if (ack_flag <= 0) {
        mlx90614_iic_stop();
        return 1; /* 超时无应答 */
    }
    MLX90614_SCL(0);
    MLX90614_SDA_OUT();
    MLX90614_SDA(0);
    return 0;
}

static void mlx90614_iic_send_byte(uint8_t dat)
{
    uint8_t i;
    MLX90614_SDA_OUT();
    MLX90614_SCL(0);
    for (i = 0; i < 8; i++) {
        MLX90614_SDA((dat & 0x80) >> 7);
        delay_us(1);
        MLX90614_SCL(1);
        delay_us(2);
        MLX90614_SCL(0);
        delay_us(2);
        dat <<= 1;
    }
}

static uint8_t mlx90614_iic_read_byte(void)
{
    uint8_t i;
    uint8_t receive = 0;
    MLX90614_SDA_IN();
    for (i = 0; i < 8; i++) {
        MLX90614_SCL(0);
        delay_us(2);
        MLX90614_SCL(1);
        delay_us(2);
        receive <<= 1;
        if (MLX90614_SDA_GET()) {
            receive |= 1;
        }
        delay_us(1);
    }
    MLX90614_SCL(0);
    return receive;
}

/* 读 16 位 RAM 单元：写命令（地址+写 → 寄存器地址）→ 重 start + 地址+读 →
 * 低 8 位（ACK）+ 高 8 位（NACK）→ 停止（页面 MLX90614_Read 时序；命令字节
 * = bit7-5（RAM 选择）+ bit4-0（地址低 5 位），页面 RegAddr 直传 0x06/0x07
 * 即此构造）。返回 0 = 成功、1 = 通信失败（无应答/超时——页面返回 0.0 与
 * 合法 0℃ 混淆，改出参 + 状态）。 */
static uint8_t mlx90614_read_word(uint8_t reg, uint16_t *raw)
{
    uint8_t low_byte;
    uint8_t high_byte;

    mlx90614_iic_start();
    mlx90614_iic_send_byte((MLX90614_ADDR << 1) | 0); /* 器件地址 + 写（0xB4） */
    if (mlx90614_iic_wait_ack() != 0) {
        return 1;
    }
    mlx90614_iic_send_byte(reg); /* 命令/寄存器地址 */
    if (mlx90614_iic_wait_ack() != 0) {
        return 1;
    }
    /* 页面此处无重试也无延时（原 delay_ms(1) 已注释）——SMBus 读连续完成 */
    mlx90614_iic_start();
    mlx90614_iic_send_byte((MLX90614_ADDR << 1) | 1); /* 器件地址 + 读（0xB5） */
    if (mlx90614_iic_wait_ack() != 0) {
        return 1;
    }
    low_byte = mlx90614_iic_read_byte(); /* 低 8 位在前（页面注释） */
    mlx90614_iic_send_ack(0);
    high_byte = mlx90614_iic_read_byte(); /* 高 8 位 */
    mlx90614_iic_send_ack(1); /* 非应答（最后一字节） */
    mlx90614_iic_stop();

    if (raw != NULL) {
        *raw = (uint16_t)(((uint16_t)high_byte << 8) | low_byte);
    }
    return 0;
}

void mlx90614_init(void)
{
    /* SMBus 器件无初始化序列（出厂校验/线性化完成，页面演示亦无 init），
     * 空实现占位保持模块 API 一致；在线校验由读温度判（无应答 = 未接）。 */
}

uint8_t mlx90614_read_object_temp(float *temp_c)
{
    uint16_t raw = 0;
    if (temp_c == NULL) {
        return 1; /* 出参必填（照 aht10_read 先例） */
    }
    if (mlx90614_read_word(MLX90614_REG_OBJECT_TEMP, &raw) != 0) {
        return 1;
    }
    /* 页面换算原式：0.02K/LSB（数据手册 0.01℃ 分辨率，页面用 0.02 系数） */
    *temp_c = (float)raw * 0.02f - 273.15f;
    return 0;
}

uint8_t mlx90614_read_ambient_temp(float *temp_c)
{
    uint16_t raw = 0;
    if (temp_c == NULL) {
        return 1; /* 出参必填（照 aht10_read 先例） */
    }
    if (mlx90614_read_word(MLX90614_REG_AMBIENT_TEMP, &raw) != 0) {
        return 1;
    }
    *temp_c = (float)raw * 0.02f - 273.15f;
    return 0;
}
