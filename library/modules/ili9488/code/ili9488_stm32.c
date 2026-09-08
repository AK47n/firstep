/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《3.5寸彩屏》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/screen/3.5-ili9488-color-screen.html
 * 驱动来源：lcdwiki MSP3520 例程包（用户网盘下载并解压）——
 *   3.5inch_SPI_Module_ILI9488_MSP3520_V1.1/1-Demo/Demo_STM32/
 *   Demo_STM32F103RCT6_Software_SPI/HARDWARE/LCD/lcd.c/h
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ili9488_stm32.h"
#include "ili9488_font.h"
#include "pin_config.h"
#include "headfile.h"

/* ===========================================================================
 * 软 SPI 总线原语（lcdwiki 软 SPI 版 SPIv_WriteData 移植：每字节 CS 低 →
 * 8 位 MSB 先 → CS 高——片选空闲高；SCL 上升沿采样，SPI 模式 0；stm32 版
 * = gpio_set 位操作——lcdwiki LCD_CS_SET/CLR 位带宏换算（不引 sys.h）；
 * 电平配置 = 包内 GPIO_Init GPIO_Mode_Out_PP → ml_gpio OUT_PP）
 * =========================================================================== */

#define ILI9488_SCL(x) gpio_set(ILI9488_SCL_GPIO, ILI9488_SCL_PIN, (x))
#define ILI9488_SDA(x) gpio_set(ILI9488_SDA_GPIO, ILI9488_SDA_PIN, (x))
#define ILI9488_RES(x) gpio_set(ILI9488_RES_GPIO, ILI9488_RES_PIN, (x))
#define ILI9488_DC(x)  gpio_set(ILI9488_DC_GPIO, ILI9488_DC_PIN, (x))
#define ILI9488_CS(x)  gpio_set(ILI9488_CS_GPIO, ILI9488_CS_PIN, (x))
#define ILI9488_BLK(x) gpio_set(ILI9488_BLK_GPIO, ILI9488_BLK_PIN, (x))

static void ili9488_writ_bus(uint8_t dat)
{
    uint8_t i;
    ILI9488_CS(0);
    for (i = 0; i < 8; i++) {
        ILI9488_SCL(0);
        if (dat & 0x80u) {
            ILI9488_SDA(1);
        } else {
            ILI9488_SDA(0);
        }
        ILI9488_SCL(1);
        dat <<= 1;
    }
    ILI9488_CS(1);
}

void ili9488_wr_reg(uint8_t dat) /* 内部：命令（DC=0） */
{
    ILI9488_DC(0);
    ili9488_writ_bus(dat);
    ILI9488_DC(1);
}

static void ili9488_wr_data8(uint8_t dat)
{
    ili9488_writ_bus(dat);
}

/* **ILI9488 18bit 面板 16bit 打包（包内 Lcd_WriteData_16Bit 原式）**：
 * 像素接口 = 0x3A 0x66（18bit RGB）——每像素 3 字节流：RED 5bit
 * （RGB565 高 5 位左对齐 0xF8）、GREEN 6bit（>>3 对齐 0xFC）、BLUE
 * 5bit（RGB565 低 5 位左对齐 3 位）——与 ILI9341（16bit 双字节）不同；
 * 全屏填充字节数 = 像素×3（性能 ≈0.55s——局部刷新建议，notes） */
void ili9488_wr_data(uint16_t dat) /* 内部：RGB565 → 18bit 3 字节 */
{
    ili9488_writ_bus((uint8_t)((dat >> 8) & 0xF8)); /* RED */
    ili9488_writ_bus((uint8_t)((dat >> 3) & 0xFC)); /* GREEN */
    ili9488_writ_bus((uint8_t)(dat << 3));           /* BLUE */
}

/* 当前方向状态（ili9488_init 设置） */
static uint16_t s_width = 320;
static uint16_t s_height = 480;

/* 方向 MADCTL 表（包内 LCD_direction 原式：BGR=1 固定——
 * dir 0 = 0x08、1 = 0x68、2 = 0xC8、3 = 0xA8） */
static const uint8_t ili9488_madctl[4] = {0x08u, 0x68u, 0xC8u, 0xA8u};

void ili9488_address_set(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2)
{
    ili9488_wr_reg(0x2A);
    ili9488_wr_data8((uint8_t)(x1 >> 8));
    ili9488_wr_data8((uint8_t)x1);
    ili9488_wr_data8((uint8_t)(x2 >> 8));
    ili9488_wr_data8((uint8_t)x2);
    ili9488_wr_reg(0x2B);
    ili9488_wr_data8((uint8_t)(y1 >> 8));
    ili9488_wr_data8((uint8_t)y1);
    ili9488_wr_data8((uint8_t)(y2 >> 8));
    ili9488_wr_data8((uint8_t)y2);
    ili9488_wr_reg(0x2C); /* 储存器写 */
}

void ili9488_init(uint8_t dir)
{
    uint8_t d = (dir & 0x03u);

    gpio_init(ILI9488_SCL_GPIO, ILI9488_SCL_PIN, OUT_PP);
    gpio_init(ILI9488_SDA_GPIO, ILI9488_SDA_PIN, OUT_PP);
    gpio_init(ILI9488_RES_GPIO, ILI9488_RES_PIN, OUT_PP);
    gpio_init(ILI9488_DC_GPIO, ILI9488_DC_PIN, OUT_PP);
    gpio_init(ILI9488_CS_GPIO, ILI9488_CS_PIN, OUT_PP);
    gpio_init(ILI9488_BLK_GPIO, ILI9488_BLK_PIN, OUT_PP);
    ILI9488_CS(1);
    ILI9488_DC(1);
    ILI9488_BLK(0);

    /* 复位脉冲（包内 LCD_RESET 原式：RST 低 100ms → 高 50ms） */
    ILI9488_RES(0);
    delay_ms(100);
    ILI9488_RES(1);
    delay_ms(50);

    /* ILI9488 初始化序列（包内 LCD_Init 原式——完整命令族；
     * 0x36 MADCTL 初值与方向表一致；0x3A = 0x66（18bit RGB——
     * 18bit 打包见 ili9488_wr_data 注释） */
    ili9488_wr_reg(0xF7);
    ili9488_wr_data8(0xA9); ili9488_wr_data8(0x51); ili9488_wr_data8(0x2C);
    ili9488_wr_data8(0x82);
    ili9488_wr_reg(0xC0);
    ili9488_wr_data8(0x11); ili9488_wr_data8(0x09);
    ili9488_wr_reg(0xC1);
    ili9488_wr_data8(0x41);
    ili9488_wr_reg(0xC5);
    ili9488_wr_data8(0x00); ili9488_wr_data8(0x0A); ili9488_wr_data8(0x80);
    ili9488_wr_reg(0xB1);
    ili9488_wr_data8(0xB0); ili9488_wr_data8(0x11);
    ili9488_wr_reg(0xB4);
    ili9488_wr_data8(0x02);
    ili9488_wr_reg(0xB6);
    ili9488_wr_data8(0x02); ili9488_wr_data8(0x42);
    ili9488_wr_reg(0xB7);
    ili9488_wr_data8(0xC6);
    ili9488_wr_reg(0xBE);
    ili9488_wr_data8(0x00); ili9488_wr_data8(0x04);
    ili9488_wr_reg(0xE9);
    ili9488_wr_data8(0x00);
    ili9488_wr_reg(0x36);
    ili9488_wr_data8(ili9488_madctl[d]);
    ili9488_wr_reg(0x3A);
    ili9488_wr_data8(0x66); /* 18bit RGB（16bit 打包 3 字节） */
    ili9488_wr_reg(0xE0);
    ili9488_wr_data8(0x00); ili9488_wr_data8(0x07); ili9488_wr_data8(0x10);
    ili9488_wr_data8(0x09); ili9488_wr_data8(0x17); ili9488_wr_data8(0x0B);
    ili9488_wr_data8(0x41); ili9488_wr_data8(0x89); ili9488_wr_data8(0x4B);
    ili9488_wr_data8(0x0A); ili9488_wr_data8(0x0C); ili9488_wr_data8(0x0E);
    ili9488_wr_data8(0x18); ili9488_wr_data8(0x1B); ili9488_wr_data8(0x0F);
    ili9488_wr_reg(0xE1);
    ili9488_wr_data8(0x00); ili9488_wr_data8(0x17); ili9488_wr_data8(0x1A);
    ili9488_wr_data8(0x04); ili9488_wr_data8(0x0E); ili9488_wr_data8(0x06);
    ili9488_wr_data8(0x2F); ili9488_wr_data8(0x45); ili9488_wr_data8(0x43);
    ili9488_wr_data8(0x02); ili9488_wr_data8(0x0A); ili9488_wr_data8(0x09);
    ili9488_wr_data8(0x32); ili9488_wr_data8(0x36); ili9488_wr_data8(0x0F);
    ili9488_wr_reg(0x11); /* Exit Sleep */
    delay_ms(120);
    ili9488_wr_reg(0x29); /* display on */

    if (d == 0 || d == 1) { /* dir 0/1 = 竖屏 320×480、2/3 = 横屏 480×320 */
        s_width = 320;
        s_height = 480;
    } else {
        s_width = 480;
        s_height = 320;
    }
    ILI9488_BLK(1); /* 开背光 */
    ili9488_clear(BLACK); /* 清全屏黑（包内白——统一库内 BLACK 口径） */
}

uint16_t ili9488_get_width(void)
{
    return s_width;
}

uint16_t ili9488_get_height(void)
{
    return s_height;
}

/* ====== 以下自 mspm0 lcd.c 移植（绘制/文本层——纯 C 零魔改） ====== */



/* ===========================================================================
 * 绘制层（厂家 lcd.c 移植：函数名规范化 ili9488_*、u16/u8 → uint16_t/uint8_t、
 * 去 main 演示/printf；绘制层不引用分辨率宏——分辨率经 ili9488_init 运行时态
 * 与 ili9488_address_set 偏移表，方向切换零重编译）
 * =========================================================================== */

/* 在指定区域填充颜色：xsta..xend-1 × ysta..yend-1（半开区间，厂家原语义） */
void ili9488_fill(uint16_t xsta, uint16_t ysta, uint16_t xend, uint16_t yend,
              uint16_t color)
{
    uint16_t i, j;
    ili9488_address_set(xsta, ysta, (uint16_t)(xend - 1), (uint16_t)(yend - 1));
    for (i = ysta; i < yend; i++) {
        for (j = xsta; j < xend; j++) {
            ili9488_wr_data(color);
        }
    }
}

/* 清全屏 */
void ili9488_clear(uint16_t color)
{
    ili9488_fill(0, 0, ili9488_get_width(), ili9488_get_height(), color);
}

/* 画点 */
void ili9488_draw_point(uint16_t x, uint16_t y, uint16_t color)
{
    ili9488_address_set(x, y, x, y);
    ili9488_wr_data(color);
}

/* 画线（Bresenham，厂家原算法） */
void ili9488_draw_line(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
                   uint16_t color)
{
    uint16_t t;
    int xerr = 0, yerr = 0, delta_x, delta_y, distance;
    int incx, incy, u_row, u_col;

    delta_x = (int)x2 - (int)x1;
    delta_y = (int)y2 - (int)y1;
    u_row = x1;
    u_col = y1;
    if (delta_x > 0) {
        incx = 1;
    } else if (delta_x == 0) {
        incx = 0;
    } else {
        incx = -1;
        delta_x = -delta_x;
    }
    if (delta_y > 0) {
        incy = 1;
    } else if (delta_y == 0) {
        incy = 0;
    } else {
        incy = -1;
        delta_y = -delta_y;
    }
    if (delta_x > delta_y) {
        distance = delta_x;
    } else {
        distance = delta_y;
    }
    for (t = 0; t < (uint16_t)(distance + 1); t++) {
        ili9488_draw_point((uint16_t)u_row, (uint16_t)u_col, color);
        xerr += delta_x;
        yerr += delta_y;
        if (xerr > distance) {
            xerr -= distance;
            u_row += incx;
        }
        if (yerr > distance) {
            yerr -= distance;
            u_col += incy;
        }
    }
}

/* 画矩形边框（四条边） */
void ili9488_draw_rectangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
                        uint16_t color)
{
    ili9488_draw_line(x1, y1, x2, y1, color);
    ili9488_draw_line(x1, y1, x1, y2, color);
    ili9488_draw_line(x1, y2, x2, y2, color);
    ili9488_draw_line(x2, y1, x2, y2, color);
}

/* 画圆（中点圆；越界由面板端自裁，驱动不裁——圆屏四角圆缺属物理特性） */
void ili9488_draw_circle(uint16_t x0, uint16_t y0, uint8_t r, uint16_t color)
{
    int a, b;
    a = 0;
    b = r;
    while (a <= b) {
        ili9488_draw_point((uint16_t)((int)x0 - b), (uint16_t)((int)y0 - a), color);
        ili9488_draw_point((uint16_t)((int)x0 + b), (uint16_t)((int)y0 - a), color);
        ili9488_draw_point((uint16_t)((int)x0 - a), (uint16_t)((int)y0 + b), color);
        ili9488_draw_point((uint16_t)((int)x0 - a), (uint16_t)((int)y0 - b), color);
        ili9488_draw_point((uint16_t)((int)x0 + b), (uint16_t)((int)y0 + a), color);
        ili9488_draw_point((uint16_t)((int)x0 + a), (uint16_t)((int)y0 - b), color);
        ili9488_draw_point((uint16_t)((int)x0 + a), (uint16_t)((int)y0 + b), color);
        ili9488_draw_point((uint16_t)((int)x0 - b), (uint16_t)((int)y0 + a), color);
        a++;
        if ((a * a + b * b) > (r * r)) {
            b--;
        }
    }
}

/* 16×16 汉字点阵写窗：sizey 应传 16（保留厂家参数字号——仅 16 有效） */
static void ili9488_show_chinese_block(uint16_t x, uint16_t y, const uint8_t *s,
                                   uint16_t fc, uint16_t bc, uint8_t sizey,
                                   uint8_t mode)
{
    uint8_t i, j, m = 0;
    uint16_t k;
    uint16_t hz_num;
    uint16_t typeface_num;
    uint16_t x0 = x;

    typeface_num = (uint16_t)((sizey / 8 + ((sizey % 8) ? 1 : 0)) * sizey);
    hz_num = (uint16_t)(sizeof(tfont16) / sizeof(typFNT_GB16));
    for (k = 0; k < hz_num; k++) {
        if ((tfont16[k].Index[0] == s[0]) && (tfont16[k].Index[1] == s[1])) {
            ili9488_address_set(x, y, (uint16_t)(x + sizey - 1),
                            (uint16_t)(y + sizey - 1));
            for (i = 0; i < typeface_num; i++) {
                for (j = 0; j < 8; j++) {
                    if (!mode) { /* 非叠加：前景/背景逐像素写 */
                        if (tfont16[k].Msk[i] & (0x01u << j)) {
                            ili9488_wr_data(fc);
                        } else {
                            ili9488_wr_data(bc);
                        }
                        m++;
                        if (m % sizey == 0) {
                            m = 0;
                            break;
                        }
                    } else { /* 叠加：只画前景点 */
                        if (tfont16[k].Msk[i] & (0x01u << j)) {
                            ili9488_draw_point(x, y, fc);
                        }
                        x++;
                        if ((x - x0) == sizey) {
                            x = x0;
                            y++;
                            break;
                        }
                    }
                }
            }
            break; /* 命中即出（厂家 continue 注释矛盾，已按注释意图修正） */
        }
    }
}

/* 显示单个字符（sizey 12 = ascii_1206 6×12、16 = ascii_1608 8×16；
 * 24/32 已裁剪——不绘制，调用方核对字号；mode = 0 非叠加/1 叠加） */
void ili9488_show_char(uint16_t x, uint16_t y, uint8_t num, uint16_t fc,
                   uint16_t bc, uint8_t sizey, uint8_t mode)
{
    uint8_t temp, sizex, t, m = 0;
    uint16_t i, typeface_num;
    uint16_t x0 = x;

    sizex = (uint8_t)(sizey / 2);
    typeface_num = (uint16_t)((sizex / 8 + ((sizex % 8) ? 1 : 0)) * sizey);
    num = (uint8_t)(num - ' '); /* 得到偏移后的值 */
    ili9488_address_set(x, y, (uint16_t)(x + sizex - 1),
                    (uint16_t)(y + sizey - 1));
    for (i = 0; i < typeface_num; i++) {
        if (sizey == 12) {
            temp = ascii_1206[num][i]; /* 6×12 字体 */
        } else if (sizey == 16) {
            temp = ascii_1608[num][i]; /* 8×16 字体 */
        } else {
            return; /* 24/32 大字号已裁剪 */
        }
        for (t = 0; t < 8; t++) {
            if (!mode) { /* 非叠加 */
                if (temp & (0x01u << t)) {
                    ili9488_wr_data(fc);
                } else {
                    ili9488_wr_data(bc);
                }
                m++;
                if (m % sizex == 0) {
                    m = 0;
                    break;
                }
            } else { /* 叠加 */
                if (temp & (0x01u << t)) {
                    ili9488_draw_point(x, y, fc);
                }
                x++;
                if ((x - x0) == sizex) {
                    x = x0;
                    y++;
                    break;
                }
            }
        }
    }
}

/* 显示字符串（'\0' 结尾；x 逐字符推进 sizey/2） */
void ili9488_show_string(uint16_t x, uint16_t y, const uint8_t *p, uint16_t fc,
                     uint16_t bc, uint8_t sizey, uint8_t mode)
{
    while (*p != '\0') {
        ili9488_show_char(x, y, *p, fc, bc, sizey, mode);
        x = (uint16_t)(x + sizey / 2);
        p++;
    }
}

/* 幂运算（厂家 mypow 保留——ili9488_show_num/float 拆位用） */
static uint32_t ili9488_pow(uint8_t m, uint8_t n)
{
    uint32_t result = 1;
    while (n--) {
        result *= m;
    }
    return result;
}

/* 显示无符号整数（len 位、高位零抑制——厂家原语义：零位补空格） */
void ili9488_show_num(uint16_t x, uint16_t y, uint16_t num, uint8_t len,
                  uint16_t fc, uint16_t bc, uint8_t sizey)
{
    uint8_t t, temp;
    uint8_t enshow = 0;
    uint8_t sizex = (uint8_t)(sizey / 2);

    for (t = 0; t < len; t++) {
        temp = (uint8_t)((num / ili9488_pow(10, (uint8_t)(len - t - 1))) % 10);
        if (enshow == 0 && t < (len - 1)) {
            if (temp == 0) {
                ili9488_show_char((uint16_t)(x + t * sizex), y, ' ', fc, bc,
                              sizey, 0);
                continue;
            }
            enshow = 1;
        }
        ili9488_show_char((uint16_t)(x + t * sizex), y, (uint8_t)(temp + 48), fc,
                      bc, sizey, 0);
    }
}

/* 显示带 2 位小数的浮点（厂家 ShowFloatNum1 语义：num×100 按 len 位拆、
 * 小数点落在倒数第 2 位——3.14 → "03.14"（len=5）；num×100 溢出上限
 * 655，使用注意） */
void ili9488_show_float(uint16_t x, uint16_t y, float num, uint8_t len,
                    uint16_t fc, uint16_t bc, uint8_t sizey)
{
    uint8_t t, temp, sizex;
    uint16_t num1;

    sizex = (uint8_t)(sizey / 2);
    num1 = (uint16_t)(num * 100);
    for (t = 0; t < len; t++) {
        temp = (uint8_t)((num1 / ili9488_pow(10, (uint8_t)(len - t - 1))) % 10);
        if (t == (len - 2)) {
            ili9488_show_char((uint16_t)(x + (len - 2) * sizex), y, '.', fc, bc,
                          sizey, 0);
            t++;
            len = (uint8_t)(len + 1);
        }
        ili9488_show_char((uint16_t)(x + t * sizex), y, (uint8_t)(temp + 48), fc,
                      bc, sizey, 0);
    }
}

/* 显示单个 16×16 汉字（s = GBK 双字节，tfont16 表内查找；表外不显示） */
void ili9488_show_chinese16x16(uint16_t x, uint16_t y, const uint8_t *s,
                           uint16_t fc, uint16_t bc, uint8_t mode)
{
    ili9488_show_chinese_block(x, y, s, fc, bc, 16, mode);
}

/* 显示图片点阵（pic = RGB565 像素流高字节在前；length×width 按行序展开） */
void ili9488_show_picture(uint16_t x, uint16_t y, uint16_t length,
                      uint16_t width, const uint8_t pic[])
{
    uint16_t i, j;
    uint32_t k = 0;

    ili9488_address_set(x, y, (uint16_t)(x + length - 1),
                    (uint16_t)(y + width - 1));
    for (i = 0; i < length; i++) {
        for (j = 0; j < width; j++) {
            ili9488_wr_data8(pic[k * 2]);
            ili9488_wr_data8(pic[k * 2 + 1]);
            k++;
        }
    }
}
