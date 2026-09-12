/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《0.96寸OLED屏》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/screen/0-96-single-spi-screen.html
 * 与《1.3寸单色OLED屏》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/screen/1-3-single-oled-screen.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "oled_extra_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 字库 = 母版 ml_oled_font.h 的 OLED_F8x16（8×16 唯一套）——**不 include
 * ml_oled_font.h 本体**（其 `const unsigned char OLED_F8x16[][]` = 全局定义
 * 非 extern，include 会与 ml_oled.o 重复定义链接错）——这里 extern 声明复用
 * 母版 ml_oled.o 内已编译的同一份字库（同芯片同字库——notes）。 */
extern const unsigned char OLED_F8x16[][16];

/* 软 SPI 位操作宏（nrf24l01/max7219 先例：GPIO 直驱、不占硬件 SPI 外设；
 * SSD1306 SPI ≤10MHz，GPIO 翻转速度满足、无需节拍延时——零扩展字节尺寸
 * 差异；电平配置 = 页面原式 GPIO_Mode_Out_PP → ml_gpio OUT_PP） */
#define OLED_SPI_SCL(x) gpio_set(OLED_SPI_SCL_GPIO, OLED_SPI_SCL_PIN, (x))
#define OLED_SPI_SDA(x) gpio_set(OLED_SPI_SDA_GPIO, OLED_SPI_SDA_PIN, (x))
#define OLED_SPI_DC(x)  gpio_set(OLED_SPI_DC_GPIO, OLED_SPI_DC_PIN, (x))
#define OLED_SPI_CS(x)  gpio_set(OLED_SPI_CS_GPIO, OLED_SPI_CS_PIN, (x))
#define OLED_SPI_RES(x) gpio_set(OLED_SPI_RES_GPIO, OLED_SPI_RES_PIN, (x))

#define OLED_CMD 0u
#define OLED_DATA 1u

/* 显存（照 mspm0 oled.c 结构：128 列 × 8 页，[144] 缓冲余量——超行写入
 * 由面板忽略；SSD1306 128×32 = 4 页（s_res 分支只影响初始化序列，
 * 显存页数由调用方按分辨率控制——128×32 用 0-3 页） */
static uint8_t oled_spi_gram[144][8];

/* 分辨率静态态（oled_set_res——须在初始化前调用） */
static uint8_t s_res = OLED_RES_128X64;

/* SH1106 静态态（oled_init_sh1106 置 1——刷新列起始偏移 0x02 分支） */
static uint8_t s_sh1106 = 0;

/* SPI 位操作写一个字节（vendor SPI 例程 OLED_WR_Byte：DC 按 mode 控、
 * CS 每字节选通/释放——SCL 上升沿采样 SPI 模式 0；收尾 DC 复 1 防误写） */
static void oled_spi_write_byte(uint8_t dat, uint8_t mode)
{
    uint8_t i;
    if (mode) {
        OLED_SPI_DC(1);
    } else {
        OLED_SPI_DC(0);
    }
    OLED_SPI_CS(0);
    for (i = 0; i < 8; i++) {
        OLED_SPI_SCL(0);
        if (dat & 0x80u) {
            OLED_SPI_SDA(1);
        } else {
            OLED_SPI_SDA(0);
        }
        OLED_SPI_SCL(1);
        dat <<= 1;
    }
    OLED_SPI_CS(1);
    OLED_SPI_DC(1);
}

static void oled_spi_cmd(uint8_t dat)
{
    oled_spi_write_byte(dat, OLED_CMD);
}

static void oled_spi_data(uint8_t dat)
{
    oled_spi_write_byte(dat, OLED_DATA);
}

void oled_set_res(uint8_t res)
{
    s_res = res ? OLED_RES_128X32 : OLED_RES_128X64;
}

void oled_spi_init(void)
{
    uint8_t i, n;

    /* 五脚 GPIO 初始化（页面原式推挽输出——ml_gpio OUT_PP；RES/CS 初始高） */
    gpio_init(OLED_SPI_SCL_GPIO, OLED_SPI_SCL_PIN, OUT_PP);
    gpio_init(OLED_SPI_SDA_GPIO, OLED_SPI_SDA_PIN, OUT_PP);
    gpio_init(OLED_SPI_DC_GPIO, OLED_SPI_DC_PIN, OUT_PP);
    gpio_init(OLED_SPI_CS_GPIO, OLED_SPI_CS_PIN, OUT_PP);
    gpio_init(OLED_SPI_RES_GPIO, OLED_SPI_RES_PIN, OUT_PP);
    OLED_SPI_CS(1);
    OLED_SPI_RES(1);

    s_sh1106 = 0;
    /* RES 200ms 低脉冲复位（页面 SPI 例程原式） */
    OLED_SPI_RES(0);
    delay_ms(200);
    OLED_SPI_RES(1);

    /* SSD1306 SPI 初始化序列（页面 0-96-single-spi + mspm0 OLED_SPI_Init
     * 同参逐字节一致——仅总线层不同；128×32 = MUX 0x1F/COM 0x00 分支） */
    oled_spi_cmd(0xAE); /* 关显示 */
    oled_spi_cmd(0x00);
    oled_spi_cmd(0x10);
    oled_spi_cmd(0x40);
    oled_spi_cmd(0x81);
    oled_spi_cmd(0xCF);
    oled_spi_cmd(0xA1);
    oled_spi_cmd(0xC8);
    oled_spi_cmd(0xA6);
    oled_spi_cmd(0xA8);
    oled_spi_cmd((s_res == OLED_RES_128X32) ? 0x1F : 0x3F); /* 1/32 或 1/64 */
    oled_spi_cmd(0xD3);
    oled_spi_cmd(0x00);
    oled_spi_cmd(0xD5);
    oled_spi_cmd(0x80);
    oled_spi_cmd(0xD9);
    oled_spi_cmd(0xF1);
    oled_spi_cmd(0xDA);
    oled_spi_cmd((s_res == OLED_RES_128X32) ? 0x00 : 0x12);
    oled_spi_cmd(0xDB);
    oled_spi_cmd(0x40);
    oled_spi_cmd(0x20);
    oled_spi_cmd(0x02); /* 页寻址模式 */
    oled_spi_cmd(0x8D);
    oled_spi_cmd(0x14); /* 电荷泵使能 */
    oled_spi_cmd(0xA4);
    oled_spi_cmd(0xA6);
    /* 先清软件显存，再开显示 + 刷新 → 无花屏 */
    for (i = 0; i < 8; i++) {
        for (n = 0; n < 128; n++) {
            oled_spi_gram[n][i] = 0;
        }
    }
    oled_spi_cmd(0xAF); /* 开显示 */
    oled_spi_refresh();
}

void oled_init_sh1106(void)
{
    uint8_t i, n;

    gpio_init(OLED_SPI_SCL_GPIO, OLED_SPI_SCL_PIN, OUT_PP);
    gpio_init(OLED_SPI_SDA_GPIO, OLED_SPI_SDA_PIN, OUT_PP);
    gpio_init(OLED_SPI_DC_GPIO, OLED_SPI_DC_PIN, OUT_PP);
    gpio_init(OLED_SPI_CS_GPIO, OLED_SPI_CS_PIN, OUT_PP);
    gpio_init(OLED_SPI_RES_GPIO, OLED_SPI_RES_PIN, OUT_PP);
    OLED_SPI_CS(1);
    OLED_SPI_RES(1);

    s_sh1106 = 1;
    OLED_SPI_RES(0);
    delay_ms(200);
    OLED_SPI_RES(1);

    /* SH1106 专属序列（页面 L116-142 原式直提——0xAD/0x8B/0x33 = 电荷泵
     * 使能 + 内供 VCC + VPP 9V；列偏移 0x02（set lower column address））
     */
    oled_spi_cmd(0xAE); /* 关显示 */
    oled_spi_cmd(0x02); /* set lower column address（SH1106 列偏移） */
    oled_spi_cmd(0x10); /* set higher column address */
    oled_spi_cmd(0x40); /* set display start line */
    oled_spi_cmd(0xB0); /* set page address */
    oled_spi_cmd(0x81); /* contract control */
    oled_spi_cmd(0xCF); /* 128 */
    oled_spi_cmd(0xA1); /* set segment remap */
    oled_spi_cmd(0xA6); /* normal / reverse */
    oled_spi_cmd(0xA8); /* multiplex ratio */
    oled_spi_cmd(0x3F); /* duty = 1/64 */
    oled_spi_cmd(0xAD); /* set charge pump enable */
    oled_spi_cmd(0x8B); /* 0x8B 内供 VCC */
    oled_spi_cmd(0x33); /* 0x30-0x33 set VPP 9V */
    oled_spi_cmd(0xC8); /* COM scan direction */
    oled_spi_cmd(0xD3); /* set display offset */
    oled_spi_cmd(0x00); /* 0x20 */
    oled_spi_cmd(0xD5); /* set osc division */
    oled_spi_cmd(0x80);
    oled_spi_cmd(0xD9); /* set pre-charge period */
    oled_spi_cmd(0x1F); /* 0x22 */
    oled_spi_cmd(0xDA); /* set COM pins */
    oled_spi_cmd(0x12);
    oled_spi_cmd(0xDB); /* set vcomh */
    oled_spi_cmd(0x40);
    for (i = 0; i < 8; i++) {
        for (n = 0; n < 128; n++) {
            oled_spi_gram[n][i] = 0;
        }
    }
    oled_spi_cmd(0xAF); /* display ON */
    oled_spi_refresh();
}

void oled_spi_refresh(void)
{
    uint8_t i, n;
    uint8_t low_col = s_sh1106 ? 0x02 : 0x00; /* SH1106 列偏移 0x02 */

    for (i = 0; i < 8; i++) {
        oled_spi_cmd((uint8_t)(0xB0 + i)); /* 页地址 */
        oled_spi_cmd(low_col);             /* 低列起始（SH1106 = 0x02） */
        oled_spi_cmd(0x10);                /* 高列起始 */
        for (n = 0; n < 128; n++) {
            oled_spi_data(oled_spi_gram[n][i]);
        }
    }
}

void oled_spi_clear(void)
{
    uint8_t i, n;
    for (i = 0; i < 8; i++) {
        for (n = 0; n < 128; n++) {
            oled_spi_gram[n][i] = 0;
        }
    }
    oled_spi_refresh();
}

/* 8×16 字符写显存（OLED_F8x16 布局：byte 0-7 = 上半页 8 列、byte 8-15 =
 * 下半页——ml_oled 同款半字节切分；y 须为 8 的倍数——页对齐） */
void oled_spi_show_char(uint8_t x, uint8_t y, char chr)
{
    uint8_t i, m;
    uint8_t page = (uint8_t)(y / 8);
    uint8_t idx = (uint8_t)(chr - ' ');

    if (chr < ' ' || chr > '~') {
        return; /* 可见字符范围（母版 ml_oled 口径） */
    }
    for (i = 0; i < 8; i++) {
        uint8_t top = OLED_F8x16[idx][i];       /* 上半页字节 */
        uint8_t bot = OLED_F8x16[idx][i + 8];   /* 下半页字节 */
        for (m = 0; m < 8; m++) {
            if (top & (0x80u >> m)) {
                oled_spi_gram[(uint8_t)(x + i)][page] |= (uint8_t)(1u << m);
            } else {
                oled_spi_gram[(uint8_t)(x + i)][page] &= (uint8_t)~(1u << m);
            }
            if (bot & (0x80u >> m)) {
                oled_spi_gram[(uint8_t)(x + i)][(uint8_t)(page + 1)] |=
                    (uint8_t)(1u << m);
            } else {
                oled_spi_gram[(uint8_t)(x + i)][(uint8_t)(page + 1)] &=
                    (uint8_t)~(1u << m);
            }
        }
    }
}

void oled_spi_show_string(uint8_t x, uint8_t y, const char *str)
{
    while (*str != '\0') {
        oled_spi_show_char(x, y, *str);
        x = (uint8_t)(x + 8);
        if (x > 120) { /* 换行（128 宽 - 8）——母版 ml_oled 同语义 */
            x = 0;
            y = (uint8_t)(y + 16);
        }
        str++;
    }
}

/* 幂运算（ml_oled OLED_Pow 语义保留——show_num 拆位用） */
static uint32_t oled_spi_pow(uint32_t x, uint32_t y)
{
    uint32_t result = 1;
    while (y--) {
        result *= x;
    }
    return result;
}

void oled_spi_show_num(uint8_t x, uint8_t y, uint32_t num, uint8_t len)
{
    uint8_t t;
    uint8_t temp;
    for (t = 0; t < len; t++) {
        temp = (uint8_t)((num / oled_spi_pow(10, (uint32_t)(len - t - 1))) % 10);
        if (temp == 0) {
            oled_spi_show_char((uint8_t)(x + 8 * t), y, '0');
        } else {
            oled_spi_show_char((uint8_t)(x + 8 * t), y, (char)(temp + '0'));
        }
    }
}

/* 双平台小写族（16×8 字符网格：像素 = (column*8, line*16)） */
void oled_spi_show_text(uint8_t line, uint8_t column, const char *text)
{
    oled_spi_show_string((uint8_t)(column * 8), (uint8_t)(line * 16), text);
}

void oled_spi_show_number(uint8_t line, uint8_t column, uint32_t number,
                          uint8_t length)
{
    oled_spi_show_num((uint8_t)(column * 8), (uint8_t)(line * 16), number,
                      length);
}
