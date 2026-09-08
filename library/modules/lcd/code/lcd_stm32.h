/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《0.96寸彩屏》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/screen/0-96-color-screen.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef LCD_STM32_H
#define LCD_STM32_H

#include <stdint.h>

/* 中景园 ZJY 系列 IPS 彩屏驱动（stm32，纯驱动切片，ADR 0009）：
 * 六屏合一单模块（与 mspm0 版决策 A 同构）——ST7735/ST7735S/ST7789V2/
 * ST7789V3/GC9A01 五个变体内嵌（初始化序列 + 分辨率 + 偏移植表，表驱动——
 * 与 mspm0 版同源，仅总线层不同），启动时按屏幕型号 lcd_init(model, dir)
 * 选择；API 与 mspm0 版**同名同型完全对齐**（lcd.h 核验：init/model 宏/
 * get_width/height/fill/clear/draw_point/line/rectangle/circle/show_char/
 * string/num/float/chinese16x16/picture——六屏差异只在一行
 * lcd_init(LCD_MODEL_*, 方向)）。
 * **分层（实施决策，notes 记录）**：mspm0 版 lcd.c 绘制层 = 纯 C（零
 * DL_GPIO）但 include mspm0 专属 lcd_init.h（ti_msp_dl_config.h → stm32
 * 不可用）→ stm32 版**单文件自实现**（lcd_stm32.c = 总线原语 + 序列表 +
 * 模型表 + 绘制层——绘制层自 mspm0 lcd.c 逐行移植零魔改、序列表/模型表自
 * mspm0 lcd_init.c 逐行移植零魔改，仅总线层换 gpio_set 位操作）；字库 =
 * **库内 lcdfont.h 双平台共用同一份文件**（mspm0 与 stm32 同文件——双平台
 * 共享先例 filter.c；files 含 code/lcdfont.h）。
 * 引脚 = pin_config.h 单源 12 宏：LCD_SCL_GPIO/_PIN 默认 PB4、LCD_SDA 默认
 * PB5、LCD_RES 默认 PA5、LCD_DC 默认 PB6、LCD_CS 默认 PB7、LCD_BLK 默认
 * PA15——**与 oled SPI 五脚组/max7219 三脚组显示族互替同脚**（一次选一块
 * 屏——大屏/小屏/数码管互替，互替同脚先例）；六脚叠「继电器+编码器方向
 * （PB4）/称重+旋钮+编码器（PB5）/火焰+ADC 组（PA5——屏×火焰不同框）/
 * 舵机+巡线（PB6）/人体红外（PB7）/蜂鸣（PA15）」——显示屏与执行件/采集
 * 件不同框、同选概率最低，同选经引脚绑定消解；**与 tp_xpt2046（配套件：
 * 1.8 触摸 = 屏+触同选）刻意错开**（mspm0 批 12 同款）；页面默认脚
 * （mspm0 板脚 PA16/PA17/PA27/PA22/PB19/PB20）不照抄；
 * **软 SPI 位操作不占硬件 SPI 外设/TIMER**（彩屏 SPI 时钟上限 ~15MHz >
 * GPIO 翻转速度——无需节拍延时；nrf24l01/max7219 先例）。
 * 对应手册（立创 wiki 地阔星移植手册）：screen--0-96-color-screen.md /
 * screen--1-28-round-color-screen.md / screen--1-3-color-screen.md /
 * screen--1-47-color-screen.md / screen--1-69-color-screen.md /
 * screen--1-8-touch-color-screen.md——与 mspm0 版同源（厂家例程
 * STM32F103C8T6 版 HARDWARE\LCD\：lcd.c/lcdfont.h/pic.h 六屏字节级一致、
 * 仅 lcd_init.c 不同，故合单模块；**F4 混写甄别**：0-96/1-47 两页软 SPI
 * 初始化块为 F4 语法（RCC_AHB1PeriphClockCmd + GPIO_Mode_OUT + OType_PP +
 * PuPd）——实施按 F1 标准库改写（ml_gpio），其余代码全 F1）。
 * 未上板（软 SPI 时序/背光/偏移真机验证留后续）。 */

/* 屏幕型号（六合一；差异 = 初始化序列 + 分辨率 + 偏移表） */
#define LCD_MODEL_096   0u  /* 0.96 寸 80×160（ST7735 —— 建议先打样的最简件） */
#define LCD_MODEL_128   1u  /* 1.28 寸 240×240 圆屏（GC9A01） */
#define LCD_MODEL_130   2u  /* 1.3 寸 240×240（ST7789V2，带字库版——外置 SPI 字库芯片
                               不随本模块入库：汉字能力 = 内嵌 tfont16 常用集） */
#define LCD_MODEL_147   3u  /* 1.47 寸 172×320（ST7789V3） */
#define LCD_MODEL_169   4u  /* 1.69 寸 240×280（ST7789V2） */
#define LCD_MODEL_180   5u  /* 1.8 寸 128×160（ST7735S；触摸 = 配套独立模块
                               tp_xpt2046，本模块零触摸耦合） */

/* 显示方向：0-3（各型号 MADCTL/分辨率/偏移按方向表切换）；
 * LCD_DIR_DEFAULT = 各型号出厂默认方向（0.96 = 2 横屏、1.28/1.3/1.69 =
 * 0 竖屏、1.47 = 2 横屏、1.8 = 1 竖屏）。 */
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
 * 宏，绘制层本就不引用分辨率，方向切换零重编译）。必须在使用其它
 * lcd_* 函数前调用（本函数内含六脚 GPIO 初始化——gpio_init OUT_PP）。 */
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

#endif /* LCD_STM32_H */
