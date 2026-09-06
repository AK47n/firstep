/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《WS2812彩灯》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/control/ws2812-color-rgb-led.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef WS2812_H
#define WS2812_H

#include <stdint.h>

/* WS2812 幻彩灯带驱动（mspm0，纯驱动切片，ADR 0009）：单 GPIO 位操作时序
 * （800kHz 数据率），内置 8 灯颜色缓冲，刷新 = 缓冲整体下发 + 复位脉冲。
 * 引脚 = 母版 syscfg 实例 WS2812 / 引脚 IN（默认 PA28，与 imu_uart 默认
 * 重叠——同选时经引脚绑定消解），SysConfig 配为强推挽输出（STD/STRONG），
 * SYSCFG_DL_init 生效，无需再逐脚初始化。
 * 颜色值 = 0xRRGGBB；内部按 WS2812 数据手册的 GRB 发送序存缓冲（在
 * ws2812_set_color 里做 R/G 换位，日常写 0xFF0000 = 红即可）。
 * 数据手册时序：1 码 = 高 580ns~1us 低 220~420ns；0 码 = 高 220~380ns
 * 低 580ns~1us；位周期约 1.25us（800kHz）。本实现用 delay 模块的
 * delay_us(1) + 0.25us 精确换算（CPUCLK_FREQ/4MHz），若实测灯不亮再
 * 微调 ws2812.c 里两处延时（真机板级行为不属于编译级验证）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/control--ws2812-color-rgb-led.md
 * （立创 wiki 地猛星移植手册，代码按模块库规范改写：去掉 printf/main.c
 * 演示、函数名规范化、引脚宏参数化、延时走 delay 模块）。 */

#define WS2812_MAX 8 /* 支持的灯数上限（颜色缓冲槽位数） */

#define WS2812_RED   0xFF0000u /* 红 */
#define WS2812_GREEN 0x00FF00u /* 绿 */
#define WS2812_BLUE  0x0000FFu /* 蓝 */
#define WS2812_BLACK 0x000000u /* 熄灭 */
#define WS2812_WHITE 0xFFFFFFu /* 白 */

/* ws2812_init：初始化（SysConfig 已配引脚，本函数清空缓冲 + 复位电平）。
 * 选 ws2812 后生成工程可直接调用；不烧录灯带也安全（引脚悬空）。 */
void ws2812_init(void);

/* ws2812_set_led_count：设置实际灯数（≤ WS2812_MAX），只下发这么多灯。 */
void ws2812_set_led_count(uint8_t count);

/* ws2812_led_count：查询当前灯数。 */
uint8_t ws2812_led_count(void);

/* ws2812_set_color：设置第 led_id 盏灯颜色（0xRRGGBB，越界忽略）。 */
void ws2812_set_color(uint8_t led_id, uint32_t color);

/* ws2812_set_rgb：三原色分别设置（等价 set_color 合成 0xRRGGBB）。 */
void ws2812_set_rgb(uint8_t led_id, uint8_t r, uint8_t g, uint8_t b);

/* ws2812_refresh：把颜色缓冲里的全部灯数据下发一遍（含 ≥280us 复位）。 */
void ws2812_refresh(void);

#endif /* WS2812_H */
