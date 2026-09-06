#ifndef __LCD_INIT_H
#define __LCD_INIT_H

#include "ti_msp_dl_config.h"
#include <stdint.h>

/* 软 SPI 位操作宏（同 nrf24l01/max7219 软 SPI 先例：GPIO 直驱、不占硬件
 * SPI 外设；彩屏 SPI 时钟上限 ~15MHz，GPIO 翻转速度满足、无需节拍延时）
 * ——LCD_SCL_SIZE 等宏由 SysConfig 按 LCD 实例 per-pin 名生成
 * （<实例>_<引脚名>_PORT / _PIN；六脚跨端口由生成器分派各口宏）。 */

#define LCD_SCL(x)                                                     \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(LCD_SCL_PORT, LCD_SCL_PIN);                \
        } else {                                                       \
            DL_GPIO_clearPins(LCD_SCL_PORT, LCD_SCL_PIN);              \
        }                                                              \
    } while (0)

#define LCD_SDA(x)                                                     \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(LCD_SDA_PORT, LCD_SDA_PIN);                \
        } else {                                                       \
            DL_GPIO_clearPins(LCD_SDA_PORT, LCD_SDA_PIN);              \
        }                                                              \
    } while (0)

#define LCD_RES(x)                                                     \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(LCD_RES_PORT, LCD_RES_PIN);                \
        } else {                                                       \
            DL_GPIO_clearPins(LCD_RES_PORT, LCD_RES_PIN);              \
        }                                                              \
    } while (0)

#define LCD_DC(x)                                                      \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(LCD_DC_PORT, LCD_DC_PIN);                  \
        } else {                                                       \
            DL_GPIO_clearPins(LCD_DC_PORT, LCD_DC_PIN);                \
        }                                                              \
    } while (0)

#define LCD_CS(x)                                                      \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(LCD_CS_PORT, LCD_CS_PIN);                  \
        } else {                                                       \
            DL_GPIO_clearPins(LCD_CS_PORT, LCD_CS_PIN);                \
        }                                                              \
    } while (0)

#define LCD_BLK(x)                                                     \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(LCD_BLK_PORT, LCD_BLK_PIN);                \
        } else {                                                       \
            DL_GPIO_clearPins(LCD_BLK_PORT, LCD_BLK_PIN);              \
        }                                                              \
    } while (0)

/* 写寄存器/数据/双字节数据（供 lcd.c 绘制层与 lcd_init.c 初始化共用）。
 * lcd_address_set 按当前型号+方向的偏移表设窗（厂家 LCD_Address_Set）。 */
void lcd_wr_reg(uint8_t dat);
void lcd_wr_data8(uint8_t dat);
void lcd_wr_data(uint16_t dat);
void lcd_address_set(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2);

/* 内部状态（lcd_init 设置；lcd_get_width/height 读）——lcd.c 的 lcd_clear
 * 与初始化共用，声明见 lcd.h 公开接口。 */

#endif /* __LCD_INIT_H */
