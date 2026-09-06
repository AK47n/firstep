#ifndef __LCD_H
#define __LCD_H

#include <stdint.h>

/* 中景园 ZJY 系列 IPS 彩屏驱动（mspm0，纯驱动切片，ADR 0009）：
 * 六屏合一单模块（批次 12 决策 A）——ST7735/ST7735S/ST7789V2/ST7789V3/GC9A01
 * 五个变体内嵌于 lcd_init.c（初始化序列 + 分辨率 + 偏移植表），启动时按
 * 屏幕型号 lcd_init(model, dir) 选择，API 与芯片差异无关（画点/线/圆/矩形/
 * 填充/字符/字符串/数字/浮点/汉字/图片——风格对齐库内 oled：出参指针、
 * 无状态机、忙等时序走库 delay）。
 * 引脚 = 母版 syscfg 实例 LCD（SCL/SDA/RES/DC/CS/BLK 六输出，软 SPI 位操作
 * 不占硬件 SPI 外设/TIMER——nrf24l01/max7219 先例；CS 初始高 = 片选空闲、
 * BLK 初始高 = 开背光；默认脚与 IR_TX/GP2Y1014/FINGERPRINT/HUIDU/JQ8900/
 * SYN6288 重叠——彩屏与红外发射/粉尘/身份/巡线/语音不同框、同选概率最低，
 * 同选时经引脚绑定消解）。
 * 对应手册（立创 wiki 地猛星移植手册）：screen--0-96-color-screen.md /
 * screen--1-28-round-color-screen.md / screen--1-3-color-screen.md /
 * screen--1-47-color-screen.md / screen--1-69-color-screen.md /
 * screen--1-8-touch-color-screen.md（厂家例程 C:\Users\luoji\Desktop\caiping\
 * 各「中景园XXXX技术资料\02-*程序源码.zip」STM32F103C8T6 版 HARDWARE\LCD\
 * ——lcd.c/lcdfont.h/pic.h 六屏字节级一致、仅 lcd_init.c 不同，故合单模块；
 * 厂家 51/STM32 平台代码已按库规范改写：软 SPI GPIO 位操作、delay 走库
 * delay 模块（delay_ms）、去 printf/main 演示、函数名规范化 lcd_*）。
 * 未上板（软 SPI 时序/背光/偏移真机验证留后续）。 */

/* 屏幕型号（六合一；差异 = lcd_init.c 内的初始化序列 + 分辨率 + 偏移表） */
#define LCD_MODEL_096   0u  /* 0.96 寸 80×160（ST7735 —— 建议先打样的最简件） */
#define LCD_MODEL_128   1u  /* 1.28 寸 240×240 圆屏（GC9A01） */
#define LCD_MODEL_130   2u  /* 1.3 寸 240×240（ST7789V2，带字库版——外置 SPI 字库芯片
                               不随本模块入库：汉字能力 = 内嵌 tfont16 常用集） */
#define LCD_MODEL_147   3u  /* 1.47 寸 172×320（ST7789V3） */
#define LCD_MODEL_169   4u  /* 1.69 寸 240×280（ST7789V2） */
#define LCD_MODEL_180   5u  /* 1.8 寸 128×160（ST7735S；触摸 = 配套独立模块
                               tp_xpt2046，本模块零触摸耦合） */

/* 显示方向：0-3（厂家例程方向宏语义——0/1 竖屏、2/3 横屏，各型号
 * MADCTL/分辨率/偏移按方向表切换）；LCD_DIR_DEFAULT = 各型号出厂默认方向
 * （0.96 = 2 横屏、1.28/1.3/1.69 = 0 竖屏、1.47 = 2 横屏、1.8 = 1 竖屏）。 */
#define LCD_DIR_DEFAULT 0xFFu

/* 常用颜色（RGB565） */
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

/* 初始化彩屏：model = LCD_MODEL_*（超出 0-5 或该型号未实现 = 空操作，调用方
 * 自行核对）；dir = 0-3 或 LCD_DIR_DEFAULT（各型号出厂方向）。完成后按方向
 * 更新内部分辨率（lcd_get_width/height 出参——不复用编译期 LCD_W/LCD_H
 * 宏，lcd.c 绘制层本就不引用分辨率，方向切换零重编译）。必须在使用其它
 * lcd_* 函数前调用（软 SPI 引脚在母版 SysConfig 已配好，无需 GPIO 初始化）。 */
void lcd_init(uint8_t model, uint8_t dir);

/* 当前方向分辨率（lcd_init 后有效）。 */
uint16_t lcd_get_width(void);
uint16_t lcd_get_height(void);

/* 区域填充：xsta..xend-1 × ysta..yend-1（半开区间——厂家原语义，越界不裁剪）。 */
void lcd_fill(uint16_t xsta, uint16_t ysta, uint16_t xend, uint16_t yend,
              uint16_t color);
/* 全屏填充（= fill(0,0,width,height,color)）。 */
void lcd_clear(uint16_t color);
/* 画点。 */
void lcd_draw_point(uint16_t x, uint16_t y, uint16_t color);
/* 画线（Bresenham）。 */
void lcd_draw_line(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
                   uint16_t color);
/* 画矩形边框（四条边）。 */
void lcd_draw_rectangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
                        uint16_t color);
/* 画圆（中点画圆；圆外裁剪 = 面板端自裁，驱动不裁——圆屏四角圆缺属面板
 * 物理特性，notes 记录）。 */
void lcd_draw_circle(uint16_t x0, uint16_t y0, uint8_t r, uint16_t color);

/* 显示单个 ASCII 字符：num = 字符码；fc/bc = 前景/背景色；sizey = 字号
 * （12 = 6×12 小字 ascii_1206、16 = 8×16 主字 ascii_1608；24/32 已裁
 * 剪——传 24/32 不绘制，notes 记录）；mode = 0 非叠加（带背景）/
 * 1 叠加（只画前景点，背景透出）。 */
void lcd_show_char(uint16_t x, uint16_t y, uint8_t num, uint16_t fc,
                   uint16_t bc, uint8_t sizey, uint8_t mode);
/* 显示字符串（'\0' 结尾；x 逐字符推进 sizey/2）。 */
void lcd_show_string(uint16_t x, uint16_t y, const uint8_t *p, uint16_t fc,
                     uint16_t bc, uint8_t sizey, uint8_t mode);
/* 显示无符号整数 len 位（高位零抑制——厂家原语义：len 位左补空格）。 */
void lcd_show_num(uint16_t x, uint16_t y, uint16_t num, uint8_t len,
                  uint16_t fc, uint16_t bc, uint8_t sizey);
/* 显示浮点（厂家 ShowFloatNum1 语义：num×100 取整数再按 len 位拆、小数点
 * 落在倒数第 2 位——固定 2 位小数；len = 显示前总位数（含小数点，如
 * 3.14 → "03.14" 传 len=5）；num×100 上限 655（整数部分 ≤6，超截断
 * 为 2 位小数+1 位整数，使用注意）。 */
void lcd_show_float(uint16_t x, uint16_t y, float num, uint8_t len,
                    uint16_t fc, uint16_t bc, uint8_t sizey);
/* 显示单个汉字（16×16）：s 指向 GBK 双字节编码（如 "中" = 0xD6 0xD0），
 * 在 lcdfont.h tfont16 表内查找——表外汉字不显示（自扩字见 lcdfont.h
 * 注释）；mode = 0 非叠加/1 叠加。 */
void lcd_show_chinese16x16(uint16_t x, uint16_t y, const uint8_t *s,
                           uint16_t fc, uint16_t bc, uint8_t mode);
/* 显示图片点阵：pic = 16 位色像素流（每像素高字节在前，RGB565；
 * length×width 像素，按行序展开——与厂家 LCD_ShowPicture 同语义）。 */
void lcd_show_picture(uint16_t x, uint16_t y, uint16_t length,
                      uint16_t width, const uint8_t pic[]);

#endif /* __LCD_H */
