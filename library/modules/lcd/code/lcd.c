#include "lcd.h"
#include "lcd_init.h"
#include "lcdfont.h"

/* ===========================================================================
 * 绘制层（厂家 lcd.c 移植：函数名规范化 lcd_*、u16/u8 → uint16_t/uint8_t、
 * 去 main 演示/printf；绘制层不引用分辨率宏——分辨率经 lcd_init 运行时态
 * 与 lcd_address_set 偏移表，方向切换零重编译）
 * =========================================================================== */

/* 在指定区域填充颜色：xsta..xend-1 × ysta..yend-1（半开区间，厂家原语义） */
void lcd_fill(uint16_t xsta, uint16_t ysta, uint16_t xend, uint16_t yend,
              uint16_t color)
{
    uint16_t i, j;
    lcd_address_set(xsta, ysta, (uint16_t)(xend - 1), (uint16_t)(yend - 1));
    for (i = ysta; i < yend; i++) {
        for (j = xsta; j < xend; j++) {
            lcd_wr_data(color);
        }
    }
}

/* 清全屏 */
void lcd_clear(uint16_t color)
{
    lcd_fill(0, 0, lcd_get_width(), lcd_get_height(), color);
}

/* 画点 */
void lcd_draw_point(uint16_t x, uint16_t y, uint16_t color)
{
    lcd_address_set(x, y, x, y);
    lcd_wr_data(color);
}

/* 画线（Bresenham，厂家原算法） */
void lcd_draw_line(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
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
        lcd_draw_point((uint16_t)u_row, (uint16_t)u_col, color);
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
void lcd_draw_rectangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
                        uint16_t color)
{
    lcd_draw_line(x1, y1, x2, y1, color);
    lcd_draw_line(x1, y1, x1, y2, color);
    lcd_draw_line(x1, y2, x2, y2, color);
    lcd_draw_line(x2, y1, x2, y2, color);
}

/* 画圆（中点圆；越界由面板端自裁，驱动不裁——圆屏四角圆缺属物理特性） */
void lcd_draw_circle(uint16_t x0, uint16_t y0, uint8_t r, uint16_t color)
{
    int a, b;
    a = 0;
    b = r;
    while (a <= b) {
        lcd_draw_point((uint16_t)((int)x0 - b), (uint16_t)((int)y0 - a), color);
        lcd_draw_point((uint16_t)((int)x0 + b), (uint16_t)((int)y0 - a), color);
        lcd_draw_point((uint16_t)((int)x0 - a), (uint16_t)((int)y0 + b), color);
        lcd_draw_point((uint16_t)((int)x0 - a), (uint16_t)((int)y0 - b), color);
        lcd_draw_point((uint16_t)((int)x0 + b), (uint16_t)((int)y0 + a), color);
        lcd_draw_point((uint16_t)((int)x0 + a), (uint16_t)((int)y0 - b), color);
        lcd_draw_point((uint16_t)((int)x0 + a), (uint16_t)((int)y0 + b), color);
        lcd_draw_point((uint16_t)((int)x0 - b), (uint16_t)((int)y0 + a), color);
        a++;
        if ((a * a + b * b) > (r * r)) {
            b--;
        }
    }
}

/* 16×16 汉字点阵写窗：sizey 应传 16（保留厂家参数字号——仅 16 有效） */
static void lcd_show_chinese_block(uint16_t x, uint16_t y, const uint8_t *s,
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
            lcd_address_set(x, y, (uint16_t)(x + sizey - 1),
                            (uint16_t)(y + sizey - 1));
            for (i = 0; i < typeface_num; i++) {
                for (j = 0; j < 8; j++) {
                    if (!mode) { /* 非叠加：前景/背景逐像素写 */
                        if (tfont16[k].Msk[i] & (0x01u << j)) {
                            lcd_wr_data(fc);
                        } else {
                            lcd_wr_data(bc);
                        }
                        m++;
                        if (m % sizey == 0) {
                            m = 0;
                            break;
                        }
                    } else { /* 叠加：只画前景点 */
                        if (tfont16[k].Msk[i] & (0x01u << j)) {
                            lcd_draw_point(x, y, fc);
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
void lcd_show_char(uint16_t x, uint16_t y, uint8_t num, uint16_t fc,
                   uint16_t bc, uint8_t sizey, uint8_t mode)
{
    uint8_t temp, sizex, t, m = 0;
    uint16_t i, typeface_num;
    uint16_t x0 = x;

    sizex = (uint8_t)(sizey / 2);
    typeface_num = (uint16_t)((sizex / 8 + ((sizex % 8) ? 1 : 0)) * sizey);
    num = (uint8_t)(num - ' '); /* 得到偏移后的值 */
    lcd_address_set(x, y, (uint16_t)(x + sizex - 1),
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
                    lcd_wr_data(fc);
                } else {
                    lcd_wr_data(bc);
                }
                m++;
                if (m % sizex == 0) {
                    m = 0;
                    break;
                }
            } else { /* 叠加 */
                if (temp & (0x01u << t)) {
                    lcd_draw_point(x, y, fc);
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
void lcd_show_string(uint16_t x, uint16_t y, const uint8_t *p, uint16_t fc,
                     uint16_t bc, uint8_t sizey, uint8_t mode)
{
    while (*p != '\0') {
        lcd_show_char(x, y, *p, fc, bc, sizey, mode);
        x = (uint16_t)(x + sizey / 2);
        p++;
    }
}

/* 幂运算（厂家 mypow 保留——lcd_show_num/float 拆位用） */
static uint32_t lcd_pow(uint8_t m, uint8_t n)
{
    uint32_t result = 1;
    while (n--) {
        result *= m;
    }
    return result;
}

/* 显示无符号整数（len 位、高位零抑制——厂家原语义：零位补空格） */
void lcd_show_num(uint16_t x, uint16_t y, uint16_t num, uint8_t len,
                  uint16_t fc, uint16_t bc, uint8_t sizey)
{
    uint8_t t, temp;
    uint8_t enshow = 0;
    uint8_t sizex = (uint8_t)(sizey / 2);

    for (t = 0; t < len; t++) {
        temp = (uint8_t)((num / lcd_pow(10, (uint8_t)(len - t - 1))) % 10);
        if (enshow == 0 && t < (len - 1)) {
            if (temp == 0) {
                lcd_show_char((uint16_t)(x + t * sizex), y, ' ', fc, bc,
                              sizey, 0);
                continue;
            }
            enshow = 1;
        }
        lcd_show_char((uint16_t)(x + t * sizex), y, (uint8_t)(temp + 48), fc,
                      bc, sizey, 0);
    }
}

/* 显示带 2 位小数的浮点（厂家 ShowFloatNum1 语义：num×100 按 len 位拆、
 * 小数点落在倒数第 2 位——3.14 → "03.14"（len=5）；num×100 溢出上限
 * 655，使用注意） */
void lcd_show_float(uint16_t x, uint16_t y, float num, uint8_t len,
                    uint16_t fc, uint16_t bc, uint8_t sizey)
{
    uint8_t t, temp, sizex;
    uint16_t num1;

    sizex = (uint8_t)(sizey / 2);
    num1 = (uint16_t)(num * 100);
    for (t = 0; t < len; t++) {
        temp = (uint8_t)((num1 / lcd_pow(10, (uint8_t)(len - t - 1))) % 10);
        if (t == (len - 2)) {
            lcd_show_char((uint16_t)(x + (len - 2) * sizex), y, '.', fc, bc,
                          sizey, 0);
            t++;
            len = (uint8_t)(len + 1);
        }
        lcd_show_char((uint16_t)(x + t * sizex), y, (uint8_t)(temp + 48), fc,
                      bc, sizey, 0);
    }
}

/* 显示单个 16×16 汉字（s = GBK 双字节，tfont16 表内查找；表外不显示） */
void lcd_show_chinese16x16(uint16_t x, uint16_t y, const uint8_t *s,
                           uint16_t fc, uint16_t bc, uint8_t mode)
{
    lcd_show_chinese_block(x, y, s, fc, bc, 16, mode);
}

/* 显示图片点阵（pic = RGB565 像素流高字节在前；length×width 按行序展开） */
void lcd_show_picture(uint16_t x, uint16_t y, uint16_t length,
                      uint16_t width, const uint8_t pic[])
{
    uint16_t i, j;
    uint32_t k = 0;

    lcd_address_set(x, y, (uint16_t)(x + length - 1),
                    (uint16_t)(y + width - 1));
    for (i = 0; i < length; i++) {
        for (j = 0; j < width; j++) {
            lcd_wr_data8(pic[k * 2]);
            lcd_wr_data8(pic[k * 2 + 1]);
            k++;
        }
    }
}
