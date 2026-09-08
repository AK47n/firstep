/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《2.8寸彩屏》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/screen/2-8-and-3.2-color-screen.html
 * 驱动来源：lcdwiki MSP2807 例程包（用户网盘下载并解压）——
 *   sources/materials/lckfb-地阔星移植手册/网盘下载/ili9341/
 *   2.8inch_SPI_Module_ILI9341_MSP2807_V1.1/
 *   1-Demo/Demo_STM32/Demo_STM32F103RCT6_Software_SPI/
 *   （**页面链接标注例程为硬件 SPI 版——包内另含 F103 软 SPI 版**
 *   HARDWARE/LCD/lcd.c/h——直接匹配母版无 ml_spi 约束，实施以软 SPI 版为准；
 *   SPI.c 仅作时序参考；FONT.H 是 lcdwiki 自带字库——按 mspm0 口径复用
 *   库内 lcdfont.h，FONT.H 不整包入库（GBK 大字号不入库））
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef ILI9341_STM32_H
#define ILI9341_STM32_H

#include <stdint.h>

/* ILI9341 2.8 寸 320×240 16bit 彩屏驱动（stm32，纯驱动切片，ADR 0009，
 * B 类——仅 stm32 平台条目、无 mspm0 对照）：软 SPI 位操作 6 脚
 * （SCL/SDA/RES/DC/CS/BLK——不占硬件 SPI 外设/TIMER；ILIT9341 SPI 时钟
 * 上限 ~10MHz，GPIO 翻转速度满足——无需节拍延时），API **照 mspm0 lcd.h
 * 风格**（与 lcd 六合一模块同构：init(dir)/get_width/height/fill/clear/
 * draw_point/line/rectangle/circle/show_char/string/num/float/
 * chinese16x16/picture——**不照 lcdwiki 旧壳** lcddev/POINT_COLOR/
 * LCD_ShowString(带 fc/bc) 弃用）；初始化序列取自 lcdwiki 包（HARDWARE/
 * LCD/lcd.c LCD_Init 原式——0xCF/0xED/0xE8/0xCB/0xF7/0xEA/0xC0/0xC1/
 * 0xC5/0xC7/0x36/0x3A 0x55/0xB1/0xB6/0xF2/0x26/0xE0/0xE1 + 0x2A/0x2B/
 * 0x11/120ms/0x29；0x36 MADCTL 按方向替换）。**引脚宏表取自包内 lcd.h**
 * （页面零引脚表——2.8 寸模块接线图 + lcd.h LCD 端口定义：SDI/SCK/LED/
 * DC/RS/RST/CS 六线 + 触摸 T_*（触摸 = **复用 tp_xpt2046 模块**——同芯
 * XPT2046，需同时选择、本模块零触摸耦合）。
 * 引脚 = pin_config.h 单源 12 宏：ILI9341_SCL_GPIO/_PIN 默认 PB4、
 * ILI9341_SDA 默认 PB5、ILI9341_RES 默认 PA5、ILI9341_DC 默认 PB6、
 * ILI9341_CS 默认 PB7、ILI9341_BLK 默认 PA15——**与 lcd 六脚组同款互替
 * （ILI 屏×中景园屏互替同脚：一次选一块屏——互替同脚先例）+ 触摸复用
 * tp_xpt2046 组（同 tp 默认脚）**；页面默认脚（lcdwiki 板 PB9/13/10/12/11）
 * 不照抄；软 SPI 位操作不占硬件 SPI 外设/TIMER。
 * 字库 = **库内 lcdfont.h**（1206/1608 ASCII + tfont16 汉字——与 lcd 模块
 * 同源同文件内容，本模块携带副本（跨模块文件引用不可行——每模块自带
 * code/ 文件；notes 记录）；FONT.H（lcdwiki 自带 GBK 大字号 36KB）不入库。
 * 性能风险（notes）：软 SPI 320×240 全屏填充 ≈0.27s——建议局部刷新，
 * 硬 SPI 方案范围外（母版无 ml_spi）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/screen--2-8-and-3.2-color-screen.md
 * + lcdwiki 官网例程包（原页 https://wiki.lckfb.com/zh-hans/dmx/module/screen/2-8-and-3.2-color-screen.html；
 * 包内用户手册/原理图/ILI9341 Datasheet——未上板（软 SPI 时序/背光/偏移
 * 真机验证留后续）。 */

/* 显示方向：0-3（0/1 竖屏 240×320、2/3 横屏 320×240——按 MADCTL 表）。
 * ILI9341 方向 MADCTL（包内 LCD_direction 原式：BGR=1 固定：
 * 0 = 0x08、1 = 0x68、2 = 0xC8、3 = 0xA8）。 */
#define ILI9341_DIR_DEFAULT 0u /* 出厂方向（包内 USE_HORIZONTAL=0） */

/* 常用颜色（RGB565——与 lcd 六合一同值） */
#define WHITE     0xFFFF
#define BLACK     0x0000
#define BLUE      0x001F
#define BRED      0xF81F
#define GRED      0xFFE0
#define GBLUE     0x07FF
#define RED       0xF800
#define MAGENTA   0xF81F
#define GREEN     0x07E0
#define CYAN      0x7FFF
#define YELLOW    0xFFE0
#define BROWN     0xBC40
#define BRRED     0xFC07
#define GRAY      0x8430
#define DARKBLUE  0x01CF
#define LIGHTBLUE 0x7D7C
#define GRAYBLUE  0x5458
#define LIGHTGREEN 0x841F
#define LGRAY     0xC618
#define LGRAYBLUE 0xA651
#define LBBLUE    0x2B12

/* 初始化彩屏（内含六脚 GPIO 初始化 + 复位脉冲 + ILI9341 序列全族 +
 * 方向 MADCTL + 背光开 + 清全屏）；dir = 0-3 或 ILI9341_DIR_DEFAULT（0）。
 * 完成后按方向更新内部分辨率（get_width/height）。 */
void ili9341_init(uint8_t dir);

/* 当前方向分辨率（ili9341_init 后有效：dir 0/1 = 240×320、2/3 = 320×240）。 */
uint16_t ili9341_get_width(void);
uint16_t ili9341_get_height(void);

/* 区域填充：xsta..xend-1 × ysta..yend-1（半开区间——越界不裁剪）。 */
void ili9341_fill(uint16_t xsta, uint16_t ysta, uint16_t xend, uint16_t yend,
                  uint16_t color);
/* 全屏填充（= fill(0,0,width,height,color)）。 */
void ili9341_clear(uint16_t color);
/* 画点。 */
void ili9341_draw_point(uint16_t x, uint16_t y, uint16_t color);
/* 画线（Bresenham）。 */
void ili9341_draw_line(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
                       uint16_t color);
/* 画矩形边框（四条边）。 */
void ili9341_draw_rectangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
                            uint16_t color);
/* 画圆（中点画圆）。 */
void ili9341_draw_circle(uint16_t x0, uint16_t y0, uint8_t r, uint16_t color);

/* 显示单个 ASCII 字符：num = 字符码；fc/bc = 前景/背景色；sizey = 字号
 * （12 = 6×12 小字 ascii_1206、16 = 8×16 主字 ascii_1608；24/32 已裁剪）；
 * mode = 0 非叠加（带背景）/1 叠加（只画前景点）。 */
void ili9341_show_char(uint16_t x, uint16_t y, uint8_t num, uint16_t fc,
                       uint16_t bc, uint8_t sizey, uint8_t mode);
/* 显示字符串（'\0' 结尾；x 逐字符推进 sizey/2）。 */
void ili9341_show_string(uint16_t x, uint16_t y, const uint8_t *p, uint16_t fc,
                         uint16_t bc, uint8_t sizey, uint8_t mode);
/* 显示无符号整数 len 位（高位零抑制——len 位左补空格）。 */
void ili9341_show_num(uint16_t x, uint16_t y, uint16_t num, uint8_t len,
                      uint16_t fc, uint16_t bc, uint8_t sizey);
/* 显示浮点（厂家 ShowFloatNum1 语义：num×100 固定 2 位小数；len 含小数点）。 */
void ili9341_show_float(uint16_t x, uint16_t y, float num, uint8_t len,
                        uint16_t fc, uint16_t bc, uint8_t sizey);
/* 显示单个汉字（16×16，GBK 双字节在 lcdfont.h tfont16 表内查找——表外不显示）。 */
void ili9341_show_chinese16x16(uint16_t x, uint16_t y, const uint8_t *s,
                               uint16_t fc, uint16_t bc, uint8_t mode);
/* 显示图片点阵（RGB565 像素流高字节在前；length×width 按行序展开）。 */
void ili9341_show_picture(uint16_t x, uint16_t y, uint16_t length,
                          uint16_t width, const uint8_t pic[]);

#endif /* ILI9341_STM32_H */
