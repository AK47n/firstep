#include "max7219.h"
#include "ti_msp_dl_config.h" /* MAX7219_DIN_PORT/PIN、MAX7219_CLK_PORT/PIN、
                                * MAX7219_CS_PORT/PIN（SysConfig 生成命名：
                                * <实例>_<引脚名>_PORT/PIN——三脚跨 GPIOA/GPIOB
                                * 两端口，生成器按引脚名分派各口宏，无组合
                                * MAX7219_PORT；输出脚不需要 _IOMUX） */

/* 寄存器地址（MAX7219 数据手册；16 位包 = 地址字节 + 数据字节，MSB 先） */
#define MAX7219_REG_NOOP         0x00u /* 空操作（级联中的非目标片） */
#define MAX7219_REG_DIGIT0       0x01u /* 位 0-7 / 行 0-7（0x01-0x08） */
#define MAX7219_REG_DECODE_MODE  0x09u
#define MAX7219_REG_INTENSITY    0x0Au
#define MAX7219_REG_SCAN_LIMIT   0x0Bu
#define MAX7219_REG_SHUTDOWN     0x0Cu
#define MAX7219_REG_DISPLAY_TEST 0x0Fu

/* 软 SPI 位操作宏（同 nrf24l01 软 SPI 先例：位操作不必占硬件 SPI 外设；
 * MAX7219 时钟上限 10MHz，GPIO 翻转速度远慢于上限，无需延时） */
#define MAX7219_DIN(x)                                                \
    do {                                                              \
        if (x) {                                                      \
            DL_GPIO_setPins(MAX7219_DIN_PORT, MAX7219_DIN_PIN);       \
        } else {                                                      \
            DL_GPIO_clearPins(MAX7219_DIN_PORT, MAX7219_DIN_PIN);     \
        }                                                             \
    } while (0)

#define MAX7219_CLK(x)                                                \
    do {                                                              \
        if (x) {                                                      \
            DL_GPIO_setPins(MAX7219_CLK_PORT, MAX7219_CLK_PIN);       \
        } else {                                                      \
            DL_GPIO_clearPins(MAX7219_CLK_PORT, MAX7219_CLK_PIN);     \
        }                                                             \
    } while (0)

#define MAX7219_CS(x)                                                 \
    do {                                                              \
        if (x) {                                                      \
            DL_GPIO_setPins(MAX7219_CS_PORT, MAX7219_CS_PIN);         \
        } else {                                                      \
            DL_GPIO_clearPins(MAX7219_CS_PORT, MAX7219_CS_PIN);       \
        }                                                             \
    } while (0)

static uint8_t s_chips = 1; /* 级联片数（默认单芯片；write_matrix 同步） */
static uint8_t s_form = MAX7219_FORM_DIGIT; /* 当前形态（clear 选空值用） */

/* 写一个 16 位包：地址字节 + 数据字节（各 8 位，MSB 先） */
static void max7219_write_byte(uint8_t dat)
{
    uint8_t i;
    for (i = 8; i >= 1; i--) {
        MAX7219_CLK(0); /* CLK 低——DIN 只在 CLK 上升沿移入，先稳定电平 */
        MAX7219_DIN((dat & 0x80u) ? 1 : 0);
        dat <<= 1;
        MAX7219_CLK(1); /* 上升沿移入一位 */
    }
}

/* 对全部片写同一寄存器（配置类：译码/亮度/扫描/掉电/测试） */
static void max7219_write_reg_all(uint8_t addr, uint8_t data)
{
    uint8_t c;
    MAX7219_CS(0);
    for (c = s_chips; c > 0; c--) {
        max7219_write_byte(addr);
        max7219_write_byte(data);
    }
    MAX7219_CS(1); /* CS 上升沿锁存 */
}

/* 对指定片写寄存器（级联：先发最远片——16 位包沿链移位，首包落最远片）；
 * 非目标片写空操作包（0x00 0x00），保持其显示不变 */
static void max7219_write_reg_chain(uint8_t chip, uint8_t addr, uint8_t data)
{
    uint8_t c;
    MAX7219_CS(0);
    for (c = s_chips; c > 0; c--) {
        if ((c - 1) == chip) {
            max7219_write_byte(addr);
            max7219_write_byte(data);
        } else {
            max7219_write_byte(MAX7219_REG_NOOP);
            max7219_write_byte(0x00u);
        }
    }
    MAX7219_CS(1);
}

void max7219_set_chip_count(uint8_t count)
{
    if (count < 1) {
        count = 1;
    }
    if (count > 4) {
        count = 4;
    }
    s_chips = count;
}

void max7219_init(uint8_t form, uint8_t brightness)
{
    if (form != MAX7219_FORM_DIGIT) {
        form = MAX7219_FORM_MATRIX; /* 形式参数非数码管 = 按点阵处理 */
    }
    s_form = form;
    if (brightness > 15u) {
        brightness = 15u;
    }
    /* 译码方式：数码管 = 全位 BCD（0xFF）；点阵 = 无译码（0x00，行直通） */
    max7219_write_reg_all(MAX7219_REG_DECODE_MODE,
                          (form == MAX7219_FORM_DIGIT) ? 0xFFu : 0x00u);
    max7219_write_reg_all(MAX7219_REG_INTENSITY, brightness);
    max7219_write_reg_all(MAX7219_REG_SCAN_LIMIT, 0x07u); /* 8 位/8 行全开 */
    max7219_write_reg_all(MAX7219_REG_SHUTDOWN, 0x01u);   /* 普通模式 */
    max7219_write_reg_all(MAX7219_REG_DISPLAY_TEST, 0x00u); /* 结束显示测试 */
    max7219_clear();
}

void max7219_write_digit(uint8_t digit, uint8_t value)
{
    if (digit < 1 || digit > 8) {
        return; /* 位号 1-8（寄存器 0x01-0x08） */
    }
    max7219_write_reg_chain(0, (uint8_t)(MAX7219_REG_DIGIT0 + digit - 1), value);
}

void max7219_write_matrix(const uint8_t *rows, uint8_t matrices)
{
    uint8_t r;
    uint8_t c;
    if (rows == NULL || matrices < 1) {
        return;
    }
    if (matrices > 4) {
        matrices = 4;
    }
    s_chips = matrices; /* 级联片数随矩阵写入参数同步 */
    for (r = 0; r < 8; r++) {
        MAX7219_CS(0);
        /* 行 r：先发最远片，再往近端——片 0 的包最后发出落在首片 */
        for (c = matrices; c > 0; c--) {
            max7219_write_byte((uint8_t)(MAX7219_REG_DIGIT0 + r));
            max7219_write_byte(rows[(uint32_t)(c - 1) * 8u + r]);
        }
        MAX7219_CS(1); /* 每行锁存（逐行刷新，无闪烁；前一行数据不被覆盖） */
    }
}

void max7219_write_reg(uint8_t chip, uint8_t addr, uint8_t data)
{
    if (chip >= s_chips) {
        return;
    }
    max7219_write_reg_chain(chip, addr, data);
}

void max7219_clear(void)
{
    uint8_t i;
    uint8_t blank = (s_form == MAX7219_FORM_DIGIT) ? 0x0Fu : 0x00u;
    for (i = 0; i < 8; i++) {
        max7219_write_reg_all((uint8_t)(MAX7219_REG_DIGIT0 + i), blank);
    }
}
