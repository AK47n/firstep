/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《WS2812彩灯》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/ws2812-color-rgb-led.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ws2812_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* WS2812 位时序（data 手册：1 码 高≥580ns / 低 220-420ns；0 码 高 220-380ns /
 * 低≥580ns；位周期 1.25us @ 800kHz）。
 * ⚠️ **页面时序按 12MHz 标注（NOP×5≈0.26-0.32us；@12MHz 一个机器周期 83ns）
 * ——本工程 72MHz（SystemInit），NOP×5≈69ns，页面脉宽标注全部作废**；按
 * 时序手册 + mspm0 版结构重写：位 1 = 高 delay_us(1) + 低 0.25us、位 0 =
 * 高 0.25us + 低 delay_us(1)；0.25us @72MHz = 18 周期 = 18 × __NOP()。
 * 页面 `for(k = 0; i < 0; i++);` 延时循环条件写反（×4：L74/L83 原理示例 +
 * L225/L234 实现段——0 次迭代脉宽全丢，照抄灯不亮）→ 不采用；页面
 * `LedId > ledsCount` off-by-one 越界（L155）→ 修正 `>=`（与 mspm0 版
 * 「越界忽略」语义同）；页面 .h 声明 setLedCount/getLedCount/RGB_LED_Write1
 * 无定义（L281-282/L289 上游残留）→ 不声明不实现（实现 = 本模块 API）。
 * 若实测灯不亮再微调两处延时（真机板级行为不属于编译级验证——notes 记录）。 */

/* 0.25us @ 72MHz（18 周期）：页面 NOP 计数法按 12MHz 标注，跨主频失效——
 * 按 CPU 周期数重算（mspm0 版 delay_cycles(CPUCLK_FREQ/4e6) 同语义） */
#define WS2812_DELAY_QUARTER_US() \
    do { \
        __NOP(); __NOP(); __NOP(); __NOP(); __NOP(); __NOP(); \
        __NOP(); __NOP(); __NOP(); __NOP(); __NOP(); __NOP(); \
        __NOP(); __NOP(); __NOP(); __NOP(); __NOP(); __NOP(); \
    } while (0)

static uint8_t s_leds[WS2812_MAX * 3]; /* 颜色数据（GRB 发送序） */
static uint8_t s_count = WS2812_MAX;   /* 实际灯数 */

void ws2812_init(void)
{
    gpio_init(WS2812_GPIO, WS2812_PIN, OUT_PP); /* 强推挽输出（页面配置） */
    s_count = WS2812_MAX;
    for (uint8_t i = 0; i < WS2812_MAX * 3; i++) {
        s_leds[i] = 0;
    }
    gpio_set(WS2812_GPIO, WS2812_PIN, 0); /* 复位电平（低） */
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
        return; /* 越界忽略（页面临界值比较 >= ——页面 LedId > ledsCount 修正） */
    }
    /* WS2812 发送序 = GRB：绿低位、红高位、蓝最低位（页面在此将绿和红色
     * 进行颠倒——日常写 0xFF0000 = 红即可） */
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
            gpio_set(WS2812_GPIO, WS2812_PIN, 1);
            delay_us(1);
            gpio_set(WS2812_GPIO, WS2812_PIN, 0);
            WS2812_DELAY_QUARTER_US();
        } else { /* 当前位为 0：高 0.25us + 低 1us */
            gpio_set(WS2812_GPIO, WS2812_PIN, 1);
            WS2812_DELAY_QUARTER_US();
            gpio_set(WS2812_GPIO, WS2812_PIN, 0);
            delay_us(1);
        }
    }
}

void ws2812_refresh(void)
{
    for (uint16_t i = 0; i < (uint16_t)s_count * 3; i++) {
        ws2812_write_byte(s_leds[i]);
    }
    /* 复位：低电平 ≥280us 让灯锁存当前数据（页面 RGB_LED_Reset） */
    gpio_set(WS2812_GPIO, WS2812_PIN, 0);
    delay_us(285);
}
