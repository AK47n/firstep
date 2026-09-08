/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《0.96寸OLED屏》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/screen/0-96-single-spi-screen.html
 * 与《1.3寸单色OLED屏》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/screen/1-3-single-oled-screen.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef OLED_EXTRA_STM32_H
#define OLED_EXTRA_STM32_H

#include <stdint.h>

/* OLED 总线/分辨率/SH1106 变体补缺口（stm32，纯驱动切片，ADR 0009，C 类
 * 口径——mspm0 批 12/07 决策 B「同芯片同 API 仅总线层」的 stm32 补录）：
 * 母版 ml_oled（stm32 内嵌，files=[] 条目）仅 I2C 128×64 硬配（OLED_Init/
 * OLED_ShowString/oled_show_text 等——**命名已被母版占用**），本文件在
 * **不触碰 I2C 路径**（零改动）的前提下补 SPI 总线变体 + 0.91 寸 128×32
 * 分辨率变体 + SH1106（1.3 寸单色）变体：
 *   oled_spi_init()      —— 软 SPI 5 脚（SCL/SDA/DC/CS/RES）位操作 +
 *                           SSD1306 SPI 初始化序列（照 mspm0 OLED_SPI_Init
 *                           同参：0xAE/0xA8 0x3F/0xDA 0x12/0x8D 0x14… 仅
 *                           总线层不同；128×32 分支 MUX=0x1F/COM=0x00）；
 *   oled_set_res(res)    —— 分辨率（OLED_RES_128X64/128X32——0.91 寸屏，
 *                           须在初始化前调用；同 mspm0 签名语义）；
 *   oled_init_sh1106()   —— SH1106 变体初始化（专属序列：0xAD（电荷泵
 *                           使能）/0x8B（内供 VCC）/0x33（VPP 9V）+ 列偏移
 *                           0x02——页面 L116-142 页内完整 A 类直提；
 *                           SH1106 ≠ SSD1306 初始化序列——独立变体函数）；
 *   oled_spi_refresh()   —— 显存刷新（SSD1306 列起始 0x00/0x10；
 *                           SH1106 列偏移 0x02（s_sh1106 分支））；
 *   oled_spi_clear/oled_spi_show_char/oled_spi_show_string/oled_spi_show_num
 *   + 双平台小写族 oled_spi_show_text/oled_spi_show_number——显存式绘制
 *   （GRAM[144][8] 照 mspm0 oled.c 结构；绘制后由 oled_spi_refresh 刷新）。
 * **API 命名说明（notes 记录）**：mspm0 侧 SPI 变体共用 OLED_Show 一族名
 * （OLED_WR_Byte 按 s_bus_spi 分发）；stm32 侧因母版 ml_oled 已占用
 * OLED_Show 一族名与 oled_show_ 小写族（I2C 路径）且**母版不可改名/不可
 * 重定义**（模块规范红线），SPI 路径全部加 `oled_spi_` 前缀（**I2C 路径
 * 零改动**——ml_oled
 * 原样；SPI 件与 I2C 件互斥使用——同一屏非总线皆可，另需引脚绑定选择）。
 * 字库 = **母版 ml_oled_font.h 的 OLED_F8x16（8×16 唯一套——stm32 母版字库
 * 口径）**——9.6KB 原样复用；6×12 小字/汉字点阵（mspm0 oledfont.h 有）在
 * stm32 母版不存在——**字号 16 唯一**（notes：汉字显示走 lcd 模块 lcdfont.h
 * tfont16，本件范围外）。
 * 引脚 = pin_config.h 单源 10 宏：OLED_SPI_SCL_GPIO/_PIN 默认 PB4、
 * OLED_SPI_SDA 默认 PB5、OLED_SPI_DC 默认 PB6、OLED_SPI_CS 默认 PB7、
 * OLED_SPI_RES 默认 PA5——与 lcd 六脚组**互替同脚**（大屏/小屏一次选一，
 * 互替同脚先例：ttp224×key_matrix；oled SPI 组 = lcd 组子集）；页面默认脚
 * (mspm0 板脚) 不照抄；软 SPI 位操作不占硬件 SPI 外设/TIMER（SSD1306 SPI
 * ≤10MHz，GPIO 翻转速度满足——无需节拍延时，nrf24l01/max7219 先例）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/screen--0-96-single-spi-screen.md
 * 与 screen--1-3-single-oled-screen.md（立创 wiki 地阔星移植手册；
 * **0-96-single-spi 页软 SPI 初始化块 F4 混写（L96-103——RCC_AHB1+OType_PP
 * +PuPd 改写 F1 ml_gpio）**；1.3 页标题「单色 OLED」实为 SH1106 128×64
 * ——mspm0 未提炼过 SH1106（同家族仅核对），本件首次落码 A 类直提；
 * 0-91 页「彩屏」标题实为 SSD1306 128×32（MUX 0x1F/COM 0x00 与 mspm0
 * oled_set_res 核验值一致——0.91 屏 = 分辨率变体非新序列）。
 * 未上板（软 SPI 时序/背光/SH1106 列偏移真机验证留后续）。 */

/* OLED 分辨率（oled_set_res——须在初始化前调用） */
#define OLED_RES_128X64 0u
#define OLED_RES_128X32 1u

/* oled_set_res：设置分辨率（128×64 默认 / 128×32——0.91 寸屏；须在
 * oled_spi_init / oled_init_sh1106 之前调用；只影响 SPI 变体初始化序列的
 * MUX/COM 分支——I2C 路径（ml_oled）零改动、不受本调用影响。 */
void oled_set_res(uint8_t res);

/* oled_spi_init：SPI 总线变体初始化（软 SPI 5 脚——RES 200ms 复位脉冲 +
 * SSD1306 序列：0xAE 关/0x00 0x10 列/0x40 起始行/0x81 对比度/0xA1/0xC8/
 * 0xA6/0xA8 0x3F 或 0x1F（s_res）/0xD3…/0x8D 0x14 电荷泵/0xAF 开——页面与
 * mspm0 同参逐字节一致，仅总线层不同），完成后显存清空 + 刷新（开机无花屏）。 */
void oled_spi_init(void);

/* oled_init_sh1106：SH1106（1.3 寸单色 OLED，128×64）变体初始化——专属
 * 序列（0xAE 关/列偏移 0x02 0x10/0x40 起始行/0xB0 页地址/0x81 0xCF/0xA1/
 * 0xA6/0xA8 0x3F/0xAD 0x8B（内供 VCC）0x33（VPP 9V）/0xC8/0xD3 0x00/
 * 0xD5 0x80/0xD9 0x1F/0xDA 0x12/0xDB 0x40/清屏/0xAF 开——页面 L116-142
 * 原式直提；SH1106 ≠ SSD1306 序列（电荷泵 0xAD vs 0x8D——独立变体函数）；
 * 其后绘制/刷新走 oled_spi_*（列偏移由内部 s_sh1106 分支 0x02）。 */
void oled_init_sh1106(void);

/* 显存刷新到屏（SSD1306 = 0xB0+页/0x00 0x10 列；SH1106 = 列起始 0x02
 * 0x10——内部分支）。 */
void oled_spi_refresh(void);

/* 显存清空 + 刷新（全屏灭）。 */
void oled_spi_clear(void);

/* 显示字符（8×16 字库 OLED_F8x16——stm32 母版唯一字号；x/y 像素坐标，
 * y 须为 8 的倍数；ml_oled 同款半字节切分语义：byte i = 列 x+i 的上半页、
 * byte i+8 = 下半页）。 */
void oled_spi_show_char(uint8_t x, uint8_t y, char chr);

/* 显示字符串（'\0' 结尾，x 逐字符推进 8 像素）。 */
void oled_spi_show_string(uint8_t x, uint8_t y, const char *str);

/* 显示无符号十进制数（len 位——高位补 '0'，ml_oled 同语义）。 */
void oled_spi_show_num(uint8_t x, uint8_t y, uint32_t num, uint8_t len);

/* 双平台小写族（16×8 字符网格：line 0-3（128×64）/0-1（128×32）、
 * column 0-15：像素 = (column*8, line*16)—mspm0 小写族同语义）。 */
void oled_spi_show_text(uint8_t line, uint8_t column, const char *text);
void oled_spi_show_number(uint8_t line, uint8_t column, uint32_t number,
                          uint8_t length);

#endif /* OLED_EXTRA_STM32_H */
