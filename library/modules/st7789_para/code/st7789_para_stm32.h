/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《1.14寸彩屏》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/screen/1-14-color-screen.html
 * 驱动来源：立创移植工程包（用户网盘下载并解压）——
 *   sources/materials/lckfb-地阔星移植手册/网盘下载/st7789_para/
 *   STM32F103C8T6_ProjectTemplate/bsp/LCD/lcd.c/h + lcd_init.c/h
 *   （ST7789V 135×240 8 位并口（8080 接口）；页面为移植教程——端口宏表/
 *   初始化序列/总线路数全部直提包内；app/main.c 演示与 bsp/uart、
 *   pic.h 演示位图不随库（mspm0 先例））
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef ST7789_PARA_STM32_H
#define ST7789_PARA_STM32_H

#include <stdint.h>

/* ST7789V 1.14 寸 135×240 8 位并口（8080 接口）彩屏驱动（stm32，纯驱动
 * 切片，ADR 0009，B 类——仅 stm32 平台条目、无 mspm0 对照）：**库内首个
 * 8 位并口显示件**——GPIO 位操作 14 脚（DB0-7 八位数据线 + RD/WR/CS/DC/
 * RES/BLK 六控制线，**不用 FSMC/硬件外设/TIMER**——8080 时序 RD/WR 选通
 * 忙等），API **照 mspm0 lcd.h 风格**（与 lcd 六合一/ili9341/ili9488 模块
 * 同构：init(dir)/get_width/height/fill/clear/draw_point/line/rectangle/
 * circle/show_char/string/num/float/chinese16x16/picture——**不照 lcdwiki
 * 旧壳** lcddev/POINT_COLOR/LCD_ShowString(带 fc/bc) 弃用）；初始化序列
 * 取自包内 lcd_init.c LCD_Init 原式（0x11/0x36(方向表)/0x3A 0x05/0xB2/
 * 0xB7/0xBB/0xC0/0xC2/0xC3/0xC4/0xC6/0xD0/0xE0/0xE1/0x21/0x29；
 * **USE_HORIZONTAL 宏方向化 = 运行时 dir 表**：MADCTL 0x00/0xC0/0x70/0xA0
 * + 地址偏移表 52/53/40/40 × 40/40/53/52——dir 0/1 竖屏 135×240、
 * 2/3 横屏 240×135，get_width/height 运行时换置零重编译；默认 =
 * 包 USE_HORIZONTAL=2 横屏）。
 * **引脚宏表 = pin_config.h 单源 28 宏**（默认脚 = 工单重拍——包默认
 * 14 脚（RD=PA5/WR=PA4/CS=PA2/DC=PA3/RES=PA1/BLK=PA0/DB0=PA6/DB1=PA7/
 * DB2=PB0/DB3=PB1/DB4=PB10/DB5=PB11/DB6=PB12/DB7=PB13）全弃用——全撞既有
 * 占用；新默认 DB0-7=PB4/5/6/7/PB0/1/PB3/PA8、RD=PA5、WR=PA4、CS=PC13、
 * DC=PC14、RES=PC15、BLK=PA15——数据线叠传感/运动/输入类（不同框同选概率
 * 最低）、控制线叠板载 LED 三灯+蜂鸣（显示替代指示互替——max7219 先例）、
 * RD/WR 叠微波+EC11/flame+ADC 组（不同框）；**与显示族（lcd/oled SPI/
 * max7219/ili 系）互替——一次只选一块屏**（14 脚现实约束：stm32 32 脚
 * 全占局面重叠面大，同选冲突经绑定消解））。
 * 字库 = **库内 lcdfont.h 同源副本 st7789_para_font.h**（1206/1608 ASCII +
 * tfont16 汉字——字符集比对结论：包内 lcdfont.h 与库内 lcdfont.h 同源
 * （ascii_1608 逐字节一致、tfont16 五字同形同阵仅 GBK 索引写法不同——
 * 包内用 C 字符串字面量、库内用 {0xD6,0xD0} 标准形式）；且 API 口径（sizey
 * 12/16 + chinese16x16）需要 ascii_1206——**包内无此套**，故采用库内
 * lcdfont.h 同源副本；**头基名全局唯一门禁 + 跨模块同名文件冲突门禁
 * （UV4 L6200E）——不引包内 lcdfont.h 名**）。
 * 性能风险（notes）：并口位操作 8 数据线并行 + CS/WR 选通——每字节
 * 12 次 gpio_set（8 位数据 + CS/WR 各下上沿），全屏 135×240×2 字节
 * ≈0.2-0.4s（估算——未上板实测留后续，建议局部刷新）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/screen--1-14-color-screen.md
 * + 立创移植工程包（原页
 * https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/screen/1-14-color-screen.html；
 * 包内 README/演示 main 剔除；页面采购链接见 manifest kit——未上板
 * （8080 时序/偏移/背光/方向真机验证留后续））。 */

/* 显示方向：0-3（dir 0/1 竖屏 135×240、2/3 横屏 240×135——按 MADCTL 表）。
 * 方向 MADCTL（包内 USE_HORIZONTAL 原式：0 = 0x00、1 = 0xC0、2 = 0x70、
 * 3 = 0xA0——与偏移表配套）。 */
#define ST7789_PARA_DIR_DEFAULT 2u /* 出厂方向（包内 USE_HORIZONTAL=2 横屏） */

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

/* 初始化彩屏（内含 14 脚 GPIO 初始化 + 复位脉冲 + ST7789V 序列全族 +
 * 方向 MADCTL + 背光开 + 清全屏）；dir = 0-3 或 ST7789_PARA_DIR_DEFAULT（2）。
 * 完成后按方向更新内部分辨率（get_width/height）。 */
void st7789_para_init(uint8_t dir);

/* 当前方向分辨率（st7789_para_init 后有效：dir 0/1 = 135×240、2/3 = 240×135）。 */
uint16_t st7789_para_get_width(void);
uint16_t st7789_para_get_height(void);

/* 区域填充：xsta..xend-1 × ysta..yend-1（半开区间——越界不裁剪）。 */
void st7789_para_fill(uint16_t xsta, uint16_t ysta, uint16_t xend, uint16_t yend,
                      uint16_t color);
/* 全屏填充（= fill(0,0,width,height,color)）。 */
void st7789_para_clear(uint16_t color);
/* 画点。 */
void st7789_para_draw_point(uint16_t x, uint16_t y, uint16_t color);
/* 画线（Bresenham）。 */
void st7789_para_draw_line(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
                           uint16_t color);
/* 画矩形边框（四条边）。 */
void st7789_para_draw_rectangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2,
                                uint16_t color);
/* 画圆（中点画圆）。 */
void st7789_para_draw_circle(uint16_t x0, uint16_t y0, uint8_t r, uint16_t color);

/* 显示单个 ASCII 字符：num = 字符码；fc/bc = 前景/背景色；sizey = 字号
 * （12 = 6×12 小字 ascii_1206、16 = 8×16 主字 ascii_1608；24/32 已裁剪）；
 * mode = 0 非叠加（带背景）/1 叠加（只画前景点）。 */
void st7789_para_show_char(uint16_t x, uint16_t y, uint8_t num, uint16_t fc,
                           uint16_t bc, uint8_t sizey, uint8_t mode);
/* 显示字符串（'\0' 结尾；x 逐字符推进 sizey/2）。 */
void st7789_para_show_string(uint16_t x, uint16_t y, const uint8_t *p, uint16_t fc,
                             uint16_t bc, uint8_t sizey, uint8_t mode);
/* 显示无符号整数 len 位（高位零抑制——len 位左补空格）。 */
void st7789_para_show_num(uint16_t x, uint16_t y, uint16_t num, uint8_t len,
                          uint16_t fc, uint16_t bc, uint8_t sizey);
/* 显示浮点（厂家 ShowFloatNum1 语义：num×100 固定 2 位小数；len 含小数点）。 */
void st7789_para_show_float(uint16_t x, uint16_t y, float num, uint8_t len,
                            uint16_t fc, uint16_t bc, uint8_t sizey);
/* 显示单个汉字（16×16，GBK 双字节在 lcdfont.h tfont16 表内查找——表外不显示）。 */
void st7789_para_show_chinese16x16(uint16_t x, uint16_t y, const uint8_t *s,
                                   uint16_t fc, uint16_t bc, uint8_t mode);
/* 显示图片点阵（RGB565 像素流高字节在前；length×width 按行序展开）。 */
void st7789_para_show_picture(uint16_t x, uint16_t y, uint16_t length,
                              uint16_t width, const uint8_t pic[]);

#endif /* ST7789_PARA_STM32_H */
