#include "i2c_probe_stm32.h"
#include "pin_config.h"
/* delay_us（位操作半周期）经 headfile.h 的 ml_delay.h 提供——stm32 侧母版延时
 * 是 ml_delay 模块（不是 mspm0 的 delay 模块，故不写 #include "delay.h"；
 * aht10_stm32 / qmc5883l_stm32 同款） */
#include "headfile.h"

/* I2C 总线原语（stm32）位操作软 I2C：照 aht10 / bh1750 / qmc5883l 先例的
 * 原语族（start / stop / wait_ack / send_byte / read_byte / send_nack），
 * 半周期 5us ≈ 100kHz 级总线速度——面对不认识的器件，宁慢勿快（多数 I2C
 * 器件 ≤400kHz，裕量充足）。SDA 方向运行时切换（写 = 开漏输出驱动、
 * 读 = 上拉输入采样），总线需板上或模块自带上拉电阻。 */
#define I2C_PROBE_SDA_OUT()  gpio_init(I2C_PROBE_SDA_GPIO, I2C_PROBE_SDA_PIN, OUT_OD)
#define I2C_PROBE_SDA_IN()   gpio_init(I2C_PROBE_SDA_GPIO, I2C_PROBE_SDA_PIN, IU)
#define I2C_PROBE_SDA_GET()  gpio_get(I2C_PROBE_SDA_GPIO, I2C_PROBE_SDA_PIN)
#define I2C_PROBE_SDA(x)     gpio_set(I2C_PROBE_SDA_GPIO, I2C_PROBE_SDA_PIN, (x))
#define I2C_PROBE_SCL(x)     gpio_set(I2C_PROBE_SCL_GPIO, I2C_PROBE_SCL_PIN, (x))

/* 7 位地址 → 总线上的读 / 写地址字节（显式两个宏，不写魔法值、也不派生
 * 「写地址 + 1」那种掩盖地址语义的写法——旧件「读地址当寄存器地址」的先例）。 */
#define I2C_PROBE_ADDR_WRITE(addr7)  ((uint8_t)(((uint8_t)(addr7) << 1) | 0x00u))
#define I2C_PROBE_ADDR_READ(addr7)   ((uint8_t)(((uint8_t)(addr7) << 1) | 0x01u))

#define I2C_PROBE_HALF_PERIOD_US 5u   /* 位操作半周期（≈100kHz 级） */

static void i2c_probe_iic_start(void)
{
    I2C_PROBE_SDA_OUT();
    I2C_PROBE_SDA(1);
    I2C_PROBE_SCL(1);
    delay_us(I2C_PROBE_HALF_PERIOD_US);
    I2C_PROBE_SDA(0);
    delay_us(I2C_PROBE_HALF_PERIOD_US);
    I2C_PROBE_SCL(0);
    delay_us(I2C_PROBE_HALF_PERIOD_US);
}

static void i2c_probe_iic_stop(void)
{
    I2C_PROBE_SDA_OUT();
    I2C_PROBE_SCL(0);
    I2C_PROBE_SDA(0);
    delay_us(I2C_PROBE_HALF_PERIOD_US);
    I2C_PROBE_SCL(1);
    I2C_PROBE_SDA(1);
    delay_us(I2C_PROBE_HALF_PERIOD_US);
}

/* 等从机应答：0 = 有应答 / 1 = 超时无应答（超时发停止条件释放总线——
 * aht10_iic_wait_ack 先例）。 */
static uint8_t i2c_probe_iic_wait_ack(void)
{
    uint8_t ack_flag = 10u;

    I2C_PROBE_SDA(1);
    delay_us(1);
    I2C_PROBE_SCL(1);
    delay_us(1);
    I2C_PROBE_SDA_IN();
    delay_us(2);
    while ((I2C_PROBE_SDA_GET() == 1u) && (ack_flag != 0u)) {
        ack_flag--;
        delay_us(3);
    }
    if (ack_flag == 0u) {
        i2c_probe_iic_stop();
        return 1u;
    }
    I2C_PROBE_SCL(0);
    I2C_PROBE_SDA_OUT();
    I2C_PROBE_SDA(0);
    return 0u;
}

static void i2c_probe_iic_send_byte(uint8_t dat)
{
    uint8_t i;

    I2C_PROBE_SDA_OUT();
    I2C_PROBE_SCL(0);
    for (i = 0u; i < 8u; i++) {
        I2C_PROBE_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        I2C_PROBE_SCL(1);
        delay_us(I2C_PROBE_HALF_PERIOD_US);
        I2C_PROBE_SCL(0);
        delay_us(I2C_PROBE_HALF_PERIOD_US);
        dat = (uint8_t)(dat << 1);
    }
}

static uint8_t i2c_probe_iic_read_byte(void)
{
    uint8_t i;
    uint8_t received = 0u;

    I2C_PROBE_SDA_IN();
    for (i = 0u; i < 8u; i++) {
        I2C_PROBE_SCL(0);
        delay_us(I2C_PROBE_HALF_PERIOD_US);
        I2C_PROBE_SCL(1);
        delay_us(I2C_PROBE_HALF_PERIOD_US);
        received = (uint8_t)(received << 1);
        if (I2C_PROBE_SDA_GET() != 0u) {
            received |= 1u;
        }
        delay_us(1);
    }
    I2C_PROBE_SCL(0);
    return received;
}

/* 读的最后一字节必须回非应答（NACK），否则从机会继续推数据、后续事务错位。 */
static void i2c_probe_iic_send_nack(void)
{
    I2C_PROBE_SDA_OUT();
    I2C_PROBE_SCL(0);
    I2C_PROBE_SDA(1);
    delay_us(I2C_PROBE_HALF_PERIOD_US);
    I2C_PROBE_SCL(1);
    delay_us(I2C_PROBE_HALF_PERIOD_US);
    I2C_PROBE_SCL(0);
    I2C_PROBE_SDA(1);
}

void i2c_probe_init(void)
{
    /* SCL / SDA 都显式配成开漏输出并置高：F1 复位后 GPIO 为浮空输入，写 ODR
     * 不生效——不显式初始化就是一条死总线（库内六件软 I2C 的批次 3 回修先例）。 */
    gpio_init(I2C_PROBE_SCL_GPIO, I2C_PROBE_SCL_PIN, OUT_OD);
    gpio_init(I2C_PROBE_SDA_GPIO, I2C_PROBE_SDA_PIN, OUT_OD);
    I2C_PROBE_SCL(1);
    I2C_PROBE_SDA(1);
    delay_us(I2C_PROBE_HALF_PERIOD_US);
}

uint8_t i2c_probe_ping(uint8_t addr7)
{
    if (addr7 > 0x7Fu) {
        return 1u;
    }
    /* 只发 START + **读地址**，跟读 1 字节（丢弃）——与 mspm0 侧**同一个问法**
     * （两平台 ping 的线上字节刻意对齐：同一个器件不能在一边说通、在一边说
     * 不通）。判定只看应答位；不发任何写数据字节。
     * 读的最后一字节照例回非应答再停止（送一个完整的数据相位，不在半途掐断）。 */
    i2c_probe_iic_start();
    i2c_probe_iic_send_byte(I2C_PROBE_ADDR_READ(addr7));
    if (i2c_probe_iic_wait_ack() != 0u) {
        return 1u; /* wait_ack 内部已发停止条件释放总线 */
    }
    (void)i2c_probe_iic_read_byte(); /* 读回的字节不参与判定、也不出参 */
    i2c_probe_iic_send_nack();
    i2c_probe_iic_stop();
    return 0u;
}

uint8_t i2c_probe_read_reg(uint8_t addr7, uint8_t reg, uint8_t *value)
{
    uint8_t got;

    if (value == 0) {
        return 1u;
    }
    if (addr7 > 0x7Fu) {
        return 1u;
    }

    /* 阶段①：写寄存器指针（START + 写地址 + 寄存器地址） */
    i2c_probe_iic_start();
    i2c_probe_iic_send_byte(I2C_PROBE_ADDR_WRITE(addr7));
    if (i2c_probe_iic_wait_ack() != 0u) {
        return 1u;
    }
    i2c_probe_iic_send_byte(reg);
    if (i2c_probe_iic_wait_ack() != 0u) {
        return 1u;
    }

    /* 阶段②：重复起始（**不发停止条件**——停止会让一部分器件复位寄存器
     * 指针、读回错值）→ 读地址 → 读 1 字节 → 非应答 → 停止 */
    i2c_probe_iic_start();
    i2c_probe_iic_send_byte(I2C_PROBE_ADDR_READ(addr7));
    if (i2c_probe_iic_wait_ack() != 0u) {
        return 1u;
    }
    got = i2c_probe_iic_read_byte();
    i2c_probe_iic_send_nack();
    i2c_probe_iic_stop();

    /* 只有整条事务走完才写出参：失败时 *value 原样不动（0x00 与失败两分） */
    *value = got;
    return 0u;
}
