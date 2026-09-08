/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《1.14寸彩屏》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/screen/1-14-color-screen.html
 * 驱动来源：立创移植工程包（用户网盘下载并解压）——
 *   1.14寸彩屏_STM32F103C8T6_ProjectTemplate/bsp/LCD/lcd.c/h + lcd_init.c/h
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "st7789_para_stm32.h"
#include "st7789_para_font.h"
#include "pin_config.h"
#include "headfile.h"

/* ===========================================================================
 * 8080 并口总线原语（立创包 LCD_Writ_Bus 移植：每字节 CS 拉低 → WR 拉低 →
 * 8 位数据线并行置数（DB7..DB0 = dat 位 7..0）→ WR 拉高（写选通上升沿）→
 * CS 拉高；RD 只用于读方向——包内/本件仅写显示，RD 保持高电平不参与；
 * stm32 版 = gpio_set 位操作——包内 GPIO_WriteBit/BIT_DBx 宏换算（不引
 * sys.h 位带宏）；电平配置 = 包内 GPIO_Init GPIO_Mode_Out_PP → ml_gpio
 * OUT_PP；**不用 FSMC/硬件外设/TIMER**）
 * =========================================================================== */

#define ST7789_PARA_DB0(x) gpio_set(ST7789_PARA_DB0_GPIO, ST7789_PARA_DB0_PIN, (x))
#define ST7789_PARA_DB1(x) gpio_set(ST7789_PARA_DB1_GPIO, ST7789_PARA_DB1_PIN, (x))
#define ST7789_PARA_DB2(x) gpio_set(ST7789_PARA_DB2_GPIO, ST7789_PARA_DB2_PIN, (x))
#define ST7789_PARA_DB3(x) gpio_set(ST7789_PARA_DB3_GPIO, ST7789_PARA_DB3_PIN, (x))
#define ST7789_PARA_DB4(x) gpio_set(ST7789_PARA_DB4_GPIO, ST7789_PARA_DB4_PIN, (x))
#define ST7789_PARA_DB5(x) gpio_set(ST7789_PARA_DB5_GPIO, ST7789_PARA_DB5_PIN, (x))
#define ST7789_PARA_DB6(x) gpio_set(ST7789_PARA_DB6_GPIO, ST7789_PARA_DB6_PIN, (x))
#define ST7789_PARA_DB7(x) gpio_set(ST7789_PARA_DB7_GPIO, ST7789_PARA_DB7_PIN, (x))
#define ST7789_PARA_RD(x)  gpio_set(ST7789_PARA_RD_GPIO, ST7789_PARA_RD_PIN, (x))
#define ST7789_PARA_WR(x)  gpio_set(ST7789_PARA_WR_GPIO, ST7789_PARA_WR_PIN, (x))
#define ST7789_PARA_CS(x)  gpio_set(ST7789_PARA_CS_GPIO, ST7789_PARA_CS_PIN, (x))
#define ST7789_PARA_DC(x)  gpio_set(ST7789_PARA_DC_GPIO, ST7789_PARA_DC_PIN, (x))
#define ST7789_PARA_RES(x) gpio_set(ST7789_PARA_RES_GPIO, ST7789_PARA_RES_PIN, (x))
#define ST7789_PARA_BLK(x) gpio_set(ST7789_PARA_BLK_GPIO, ST7789_PARA_BLK_PIN, (x))

static void st7789_para_writ_bus(uint8_t dat)
{
    ST7789_PARA_CS(0);
    ST7789_PARA_WR(0);

    ST7789_PARA_DB7((dat >> 7) & 0x01u);
    ST7789_PARA_DB6((dat >> 6) & 0x01u);
    ST7789_PARA_DB5((dat >> 5) & 0x01u);
    ST7789_PARA_DB4((dat >> 4) & 0x01u);
    ST7789_PARA_DB3((dat >> 3) & 0x01u);
    ST7789_PARA_DB2((dat >> 2) & 0x01u);
    ST7789_PARA_DB1((dat >> 1) & 0x01u);
    ST7789_PARA_DB0((dat >> 0) & 0x01u);

    ST7789_PARA_WR(1);
    ST7789_PARA_CS(1);
}

static void st7789_para_wr_reg(uint8_t dat) /* 内部：命令（DC=0） */
{
    ST7789_PARA_DC(0);
    st7789_para_writ_bus(dat);
    ST7789_PARA_DC(1);
}

static void st7789_para_wr_data8(uint8_t dat)
{
    st7789_para_writ_bus(dat);
}

static void st7789_para_wr_data(uint16_t dat) /* 内部：RGB565 双字节 */
{
    st7789_para_writ_bus((uint8_t)(dat >> 8));
    st7789_para_writ_bus((uint8_t)dat);
}

/* 当前方向状态（st7789_para_init 设置） */
static uint8_t s_dir = ST7789_PARA_DIR_DEFAULT;
static uint16_t s_width = 240;
static uint16_t s_height = 135;

/* 方向 MADCTL 表（包内 USE_HORIZONTAL 原式：
 * dir 0 = 0x00、1 = 0xC0、2 = 0x70、3 = 0xA0） */
static const uint8_t st7789_para_madctl[4] = {0x00u, 0xC0u, 0x70u, 0xA0u};
/* 地址窗口偏移表（包内 LCD_Address_Set 原式：
 * dir 0 列 +52/行 +40、1 列 +53/行 +40、2 列 +40/行 +53、3 列 +40/行 +52） */
static const uint8_t st7789_para_off_x[4] = {52u, 53u, 40u, 40u};
static const uint8_t st7789_para_off_y[4] = {40u, 40u, 53u, 52u};

static void st7789_para_address_set(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2)
{
    uint8_t d = (uint8_t)(s_dir & 0x03u);

    st7789_para_wr_reg(0x2A); /* 列地址设置 */
    st7789_para_wr_data((uint16_t)(x1 + st7789_para_off_x[d]));
    st7789_para_wr_data((uint16_t)(x2 + st7789_para_off_x[d]));
    st7789_para_wr_reg(0x2B); /* 行地址设置 */
    st7789_para_wr_data((uint16_t)(y1 + st7789_para_off_y[d]));
    st7789_para_wr_data((uint16_t)(y2 + st7789_para_off_y[d]));
    st7789_para_wr_reg(0x2C); /* 储存器写 */
}

void st7789_para_init(uint8_t dir)
{
    uint8_t d = (uint8_t)(dir & 0x03u);

    /* 14 脚 GPIO 推挽输出（包内 LCD_GPIO_Init 换算：GPIO_Mode_Out_PP →
     * ml_gpio OUT_PP；先全部拉高——包内 GPIO_SetBits 原式） */
    gpio_init(ST7789_PARA_DB0_GPIO, ST7789_PARA_DB0_PIN, OUT_PP);
    gpio_init(ST7789_PARA_DB1_GPIO, ST7789_PARA_DB1_PIN, OUT_PP);
    gpio_init(ST7789_PARA_DB2_GPIO, ST7789_PARA_DB2_PIN, OUT_PP);
    gpio_init(ST7789_PARA_DB3_GPIO, ST7789_PARA_DB3_PIN, OUT_PP);
    gpio_init(ST7789_PARA_DB4_GPIO, ST7789_PARA_DB4_PIN, OUT_PP);
    gpio_init(ST7789_PARA_DB5_GPIO, ST7789_PARA_DB5_PIN, OUT_PP);
    gpio_init(ST7789_PARA_DB6_GPIO, ST7789_PARA_DB6_PIN, OUT_PP);
    gpio_init(ST7789_PARA_DB7_GPIO, ST7789_PARA_DB7_PIN, OUT_PP);
    gpio_init(ST7789_PARA_RD_GPIO, ST7789_PARA_RD_PIN, OUT_PP);
    gpio_init(ST7789_PARA_WR_GPIO, ST7789_PARA_WR_PIN, OUT_PP);
    gpio_init(ST7789_PARA_CS_GPIO, ST7789_PARA_CS_PIN, OUT_PP);
    gpio_init(ST7789_PARA_DC_GPIO, ST7789_PARA_DC_PIN, OUT_PP);
    gpio_init(ST7789_PARA_RES_GPIO, ST7789_PARA_RES_PIN, OUT_PP);
    gpio_init(ST7789_PARA_BLK_GPIO, ST7789_PARA_BLK_PIN, OUT_PP);
    ST7789_PARA_DB0(1); ST7789_PARA_DB1(1); ST7789_PARA_DB2(1);
    ST7789_PARA_DB3(1); ST7789_PARA_DB4(1); ST7789_PARA_DB5(1);
    ST7789_PARA_DB6(1); ST7789_PARA_DB7(1);
    ST7789_PARA_RD(1); ST7789_PARA_WR(1); ST7789_PARA_CS(1);
    ST7789_PARA_DC(1); ST7789_PARA_RES(1); ST7789_PARA_BLK(1);

    /* 复位脉冲（包内 LCD_Init 原式：RES 低 100ms → 高 100ms） */
    ST7789_PARA_RES(0);
    delay_ms(100);
    ST7789_PARA_RES(1);
    delay_ms(100);

    ST7789_PARA_BLK(1); /* 打开背光 */
    delay_ms(100);

    /* ST7789V 初始化序列（包内 LCD_Init 原式直提——完整 14byte 命令族；
     * 0x36 MADCTL 按方向表、0x3A 0x05 = 16bit 色（65K RGB） */
    st7789_para_wr_reg(0x11); /* Exit Sleep */
    delay_ms(120);
    st7789_para_wr_reg(0x36); /* MADCTL 方向 */
    st7789_para_wr_data8(st7789_para_madctl[d]);
    st7789_para_wr_reg(0x3A); /* 像素格式 */
    st7789_para_wr_data8(0x05); /* 16bit 色 */
    st7789_para_wr_reg(0xB2);
    st7789_para_wr_data8(0x0C); st7789_para_wr_data8(0x0C);
    st7789_para_wr_data8(0x00); st7789_para_wr_data8(0x33);
    st7789_para_wr_data8(0x33);
    st7789_para_wr_reg(0xB7);
    st7789_para_wr_data8(0x35);
    st7789_para_wr_reg(0xBB);
    st7789_para_wr_data8(0x19);
    st7789_para_wr_reg(0xC0);
    st7789_para_wr_data8(0x2C);
    st7789_para_wr_reg(0xC2);
    st7789_para_wr_data8(0x01);
    st7789_para_wr_reg(0xC3);
    st7789_para_wr_data8(0x12);
    st7789_para_wr_reg(0xC4);
    st7789_para_wr_data8(0x20);
    st7789_para_wr_reg(0xC6);
    st7789_para_wr_data8(0x0F);
    st7789_para_wr_reg(0xD0);
    st7789_para_wr_data8(0xA4); st7789_para_wr_data8(0xA1);
    st7789_para_wr_reg(0xE0); /* 正 gamma 14byte */
    st7789_para_wr_data8(0xD0); st7789_para_wr_data8(0x04);
    st7789_para_wr_data8(0x0D); st7789_para_wr_data8(0x11);
    st7789_para_wr_data8(0x13); st7789_para_wr_data8(0x2B);
    st7789_para_wr_data8(0x3F); st7789_para_wr_data8(0x54);
    st7789_para_wr_data8(0x4C); st7789_para_wr_data8(0x18);
    st7789_para_wr_data8(0x0D); st7789_para_wr_data8(0x0B);
    st7789_para_wr_data8(0x1F); st7789_para_wr_data8(0x23);
    st7789_para_wr_reg(0xE1); /* 负 gamma 14byte */
    st7789_para_wr_data8(0xD0); st7789_para_wr_data8(0x04);
    st7789_para_wr_data8(0x0C); st7789_para_wr_data8(0x11);
    st7789_para_wr_data8(0x13); st7789_para_wr_data8(0x2C);
    st7789_para_wr_data8(0x3F); st7789_para_wr_data8(0x44);
    st7789_para_wr_data8(0x51); st7789_para_wr_data8(0x2F);
    st7789_para_wr_data8(0x1F); st7789_para_wr_data8(0x1F);
    st7789_para_wr_data8(0x20); st7789_para_wr_data8(0x23);
    st7789_para_wr_reg(0x21); /* 显示反色开（包内原式——INVON） */
    st7789_para_wr_reg(0x29); /* display on */

    s_dir = d;
    if (d == 0 || d == 1) { /* dir 0/1 = 竖屏 135×240、2/3 = 横屏 240×135 */
        s_width = 135;
        s_height = 240;
    } else {
        s_width = 240;
        s_height = 135;
    }
    st7789_para_clear(BLACK); /* 清全屏黑（包内白——统一库内 BLACK 口径） */
}

uint16_t st7789_para_get_width(void)
{
    return s_width;
}

uint16_t st7789_para_get_height(void)
{
    return s_height;
}

/* ====== 以下自 mspm0 lcd.c 移植（绘制/文本层——纯 C 零魔改） ====== */



/* ===========================================================================
 * 绘制层（厂家 lcd.c 移植：函数名规范化 st7789_para_*、u16/u8 → uint16_t/
 * uint8_t、去 main 演示/printf；绘制层不引用分辨率宏——分辨率经
 * st7789_para_init 运行时态与 st7789_para_address_set 偏移表，
 * 方向切换零重编译）
 * =========================================================================== */

/* 在指定区域填充颜色：xsta..xend-1 × ysta..yend-1（半开区间，厂家原语义） */
void st7789_para_fill(uint16_t xsta, uint16_t ysta, uint16_t xend, uint16_t yend,
                      uint16_t color)
{
    uint16_t i, j;
    st7789_para_address_set(xsta, ysta, (uint16_t)(xend - 1), (uint16_t)(yend - 1));
    for (i = ysta; i < yend; i++) {
        for (j = xsta; j < xend; j++) {
            st7789_para_wr_data(color);
        }
    }
}

/* 清全屏 */
void st7789_para_clear(uint16_t color)
{
    st7789_para_fill(0, 0, st7789_para_get_width(), st7789_para_get_height(), color);
}

/* 画点 */
void st7789_para_draw_point(uint16_t x, uint16_t y, uint16_t color)
{
    st7789_para_address_set(x, y, x, y);
    st7789_para_wr_data(color);
}

/* 画线（Bresenham，厂家原算法） */
void st7789_para_draw_line(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
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
        st7789_para_draw_point((uint16_t)u_row, (uint16_t)u_col, color);
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
void st7789_para_draw_rectangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
                                uint16_t color)
{
    st7789_para_draw_line(x1, y1, x2, y1, color);
    st7789_para_draw_line(x1, y1, x1, y2, color);
    st7789_para_draw_line(x1, y2, x2, y2, color);
    st7789_para_draw_line(x2, y1, x2, y2, color);
}

/* 画圆（中点圆；越界由面板端自裁，驱动不裁——圆屏四角圆缺属物理特性） */
void st7789_para_draw_circle(uint16_t x0, uint16_t y0, uint8_t r, uint16_t color)
{
    int a, b;
    a = 0;
    b = r;
    while (a <= b) {
        st7789_para_draw_point((uint16_t)((int)x0 - b), (uint16_t)((int)y0 - a), color);
        st7789_para_draw_point((uint16_t)((int)x0 + b), (uint16_t)((int)y0 - a), color);
        st7789_para_draw_point((uint16_t)((int)x0 - a), (uint16_t)((int)y0 + b), color);
        st7789_para_draw_point((uint16_t)((int)x0 - a), (uint16_t)((int)y0 - b), color);
        st7789_para_draw_point((uint16_t)((int)x0 + b), (uint16_t)((int)y0 + a), color);
        st7789_para_draw_point((uint16_t)((int)x0 + a), (uint16_t)((int)y0 - b), color);
        st7789_para_draw_point((uint16_t)((int)x0 + a), (uint16_t)((int)y0 + b), color);
        st7789_para_draw_point((uint16_t)((int)x0 - b), (uint16_t)((int)y0 + a), color);
        a++;
        if ((a * a + b * b) > (r * r)) {
            b--;
        }
    }
}

/* 16×16 汉字点阵写窗：sizey 应传 16（保留厂家参数字号——仅 16 有效） */
static void st7789_para_show_chinese_block(uint16_t x, uint16_t y, const uint8_t *s,
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
            st7789_para_address_set(x, y, (uint16_t)(x + sizey - 1),
                                    (uint16_t)(y + sizey - 1));
            for (i = 0; i < typeface_num; i++) {
                for (j = 0; j < 8; j++) {
                    if (!mode) { /* 非叠加：前景/背景逐像素写 */
                        if (tfont16[k].Msk[i] & (0x01u << j)) {
                            st7789_para_wr_data(fc);
                        } else {
                            st7789_para_wr_data(bc);
                        }
                        m++;
                        if (m % sizey == 0) {
                            m = 0;
                            break;
                        }
                    } else { /* 叠加：只画前景点 */
                        if (tfont16[k].Msk[i] & (0x01u << j)) {
                            st7789_para_draw_point(x, y, fc);
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
void st7789_para_show_char(uint16_t x, uint16_t y, uint8_t num, uint16_t fc,
                           uint16_t bc, uint8_t sizey, uint8_t mode)
{
    uint8_t temp, sizex, t, m = 0;
    uint16_t i, typeface_num;
    uint16_t x0 = x;

    sizex = (uint8_t)(sizey / 2);
    typeface_num = (uint16_t)((sizex / 8 + ((sizex % 8) ? 1 : 0)) * sizey);
    num = (uint8_t)(num - ' '); /* 得到偏移后的值 */
    st7789_para_address_set(x, y, (uint16_t)(x + sizex - 1),
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
                    st7789_para_wr_data(fc);
                } else {
                    st7789_para_wr_data(bc);
                }
                m++;
                if (m % sizex == 0) {
                    m = 0;
                    break;
                }
            } else { /* 叠加 */
                if (temp & (0x01u << t)) {
                    st7789_para_draw_point(x, y, fc);
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
void st7789_para_show_string(uint16_t x, uint16_t y, const uint8_t *p, uint16_t fc,
                             uint16_t bc, uint8_t sizey, uint8_t mode)
{
    while (*p != '\0') {
        st7789_para_show_char(x, y, *p, fc, bc, sizey, mode);
        x = (uint16_t)(x + sizey / 2);
        p++;
    }
}

/* 幂运算（厂家 mypow 保留——st7789_para_show_num/float 拆位用） */
static uint32_t st7789_para_pow(uint8_t m, uint8_t n)
{
    uint32_t result = 1;
    while (n--) {
        result *= m;
    }
    return result;
}

/* 显示无符号整数（len 位、高位零抑制——厂家原语义：零位补空格） */
void st7789_para_show_num(uint16_t x, uint16_t y, uint16_t num, uint8_t len,
                          uint16_t fc, uint16_t bc, uint8_t sizey)
{
    uint8_t t, temp;
    uint8_t enshow = 0;
    uint8_t sizex = (uint8_t)(sizey / 2);

    for (t = 0; t < len; t++) {
        temp = (uint8_t)((num / st7789_para_pow(10, (uint8_t)(len - t - 1))) % 10);
        if (enshow == 0 && t < (len - 1)) {
            if (temp == 0) {
                st7789_para_show_char((uint16_t)(x + t * sizex), y, ' ', fc, bc,
                                      sizey, 0);
                continue;
            }
            enshow = 1;
        }
        st7789_para_show_char((uint16_t)(x + t * sizex), y, (uint8_t)(temp + 48), fc,
                              bc, sizey, 0);
    }
}

/* 显示带 2 位小数的浮点（厂家 ShowFloatNum1 语义：num×100 按 len 位拆、
 * 小数点落在倒数第 2 位——3.14 → "03.14"（len=5）；num×100 溢出上限
 * 655，使用注意） */
void st7789_para_show_float(uint16_t x, uint16_t y, float num, uint8_t len,
                            uint16_t fc, uint16_t bc, uint8_t sizey)
{
    uint8_t t, temp, sizex;
    uint16_t num1;

    sizex = (uint8_t)(sizey / 2);
    num1 = (uint16_t)(num * 100);
    for (t = 0; t < len; t++) {
        temp = (uint8_t)((num1 / st7789_para_pow(10, (uint8_t)(len - t - 1))) % 10);
        if (t == (len - 2)) {
            st7789_para_show_char((uint16_t)(x + (len - 2) * sizex), y, '.', fc, bc,
                                  sizey, 0);
            t++;
            len = (uint8_t)(len + 1);
        }
        st7789_para_show_char((uint16_t)(x + t * sizex), y, (uint8_t)(temp + 48), fc,
                              bc, sizey, 0);
    }
}

/* 显示单个 16×16 汉字（s = GBK 双字节，tfont16 表内查找；表外不显示） */
void st7789_para_show_chinese16x16(uint16_t x, uint16_t y, const uint8_t *s,
                                   uint16_t fc, uint16_t bc, uint8_t mode)
{
    st7789_para_show_chinese_block(x, y, s, fc, bc, 16, mode);
}

/* 显示图片点阵（pic = RGB565 像素流高字节在前；length×width 按行序展开） */
void st7789_para_show_picture(uint16_t x, uint16_t y, uint16_t length,
                              uint16_t width, const uint8_t pic[])
{
    uint16_t i, j;
    uint32_t k = 0;

    st7789_para_address_set(x, y, (uint16_t)(x + length - 1),
                            (uint16_t)(y + width - 1));
    for (i = 0; i < length; i++) {
        for (j = 0; j < width; j++) {
            st7789_para_wr_data8(pic[k * 2]);
            st7789_para_wr_data8(pic[k * 2 + 1]);
            k++;
        }
    }
}
