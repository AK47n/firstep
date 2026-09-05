#include "ws2812.h"
#include "delay.h" /* delay_ms / delay_us：时序延时走库内 delay 模块（依赖已声明） */
#include "ti_msp_dl_config.h" /* WS2812_PORT / WS2812_IN_PIN / CPUCLK_FREQ */

/* WS2812 位时序（data 手册：1 码高≥580ns / 低 220-420ns；0 码高 220-380ns /
 * 低≥580ns；位周期 1.25us @ 800kHz）。立创原版用 delay_us(1) + 0.25us 空
 * 循环（@12MHz 调试），本实现把 0.25us 按 CPUCLK_FREQ 精确换算，32MHz
 * 下 0.25us = 8 周期。 */

#define WS2812_DELAY_QUARTER_US() delay_cycles(CPUCLK_FREQ / 4000000)

static uint8_t s_leds[WS2812_MAX * 3]; /* 颜色数据（GRB 发送序） */
static uint8_t s_count = WS2812_MAX;   /* 实际灯数 */

void ws2812_init(void)
{
    s_count = WS2812_MAX;
    for (uint8_t i = 0; i < WS2812_MAX * 3; i++) {
        s_leds[i] = 0;
    }
    DL_GPIO_clearPins(WS2812_PORT, WS2812_IN_PIN); /* 复位电平（低） */
}

void ws2812_set_led_count(uint8_t count)
{
    if (count > WS2812_MAX) {
        count = WS2812_MAX;
    }
    s_count = count;
}

uint8_t ws2812_led_count(void)
{
    return s_count;
}

void ws2812_set_color(uint8_t led_id, uint32_t color)
{
    if (led_id >= s_count) {
        return; /* to avoid overflow */
    }
    /* WS2812 发送序 = GRB：绿低位、红高位、蓝最低位 */
    s_leds[led_id * 3 + 0] = (uint8_t)((color >> 8) & 0xFF);  /* G */
    s_leds[led_id * 3 + 1] = (uint8_t)((color >> 16) & 0xFF); /* R */
    s_leds[led_id * 3 + 2] = (uint8_t)((color >> 0) & 0xFF);  /* B */
}

void ws2812_set_rgb(uint8_t led_id, uint8_t r, uint8_t g, uint8_t b)
{
    ws2812_set_color(led_id, ((uint32_t)r << 16) | ((uint32_t)g << 8) | b);
}

static void ws2812_write_byte(uint8_t byte)
{
    for (uint8_t i = 0; i < 8; i++) {
        if (byte & (0x80 >> i)) { /* 当前位为 1：高 1us + 低 0.25us */
            DL_GPIO_setPins(WS2812_PORT, WS2812_IN_PIN);
            delay_us(1);
            DL_GPIO_clearPins(WS2812_PORT, WS2812_IN_PIN);
            WS2812_DELAY_QUARTER_US();
        } else { /* 当前位为 0：高 0.25us + 低 1us */
            DL_GPIO_setPins(WS2812_PORT, WS2812_IN_PIN);
            WS2812_DELAY_QUARTER_US();
            DL_GPIO_clearPins(WS2812_PORT, WS2812_IN_PIN);
            delay_us(1);
        }
    }
}

void ws2812_refresh(void)
{
    for (uint16_t i = 0; i < (uint16_t)s_count * 3; i++) {
        ws2812_write_byte(s_leds[i]);
    }
    /* 复位：低电平 ≥280us 让灯锁存当前数据 */
    DL_GPIO_clearPins(WS2812_PORT, WS2812_IN_PIN);
    delay_us(285);
}
