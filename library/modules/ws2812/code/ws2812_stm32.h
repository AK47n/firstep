/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《WS2812彩灯》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/ws2812-color-rgb-led.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef WS2812_STM32_H
#define WS2812_STM32_H

#include <stdint.h>

/* WS2812 幻彩灯带驱动（stm32，纯驱动切片，ADR 0009）：单 GPIO 位操作时序
 * （800kHz 数据率），内置 8 灯颜色缓冲，刷新 = 缓冲整体下发 + 复位脉冲。
 * 引脚 = pin_config.h 单源 WS2812_GPIO/WS2812_PIN（默认 PA8——与 ir_beam
 * 对射 + pid 灰度 GRAY_D5 默认重叠：幻彩灯带与「红外对射/巡线」不同框、
 * 同选概率最低（刻意不叠灯族 LED PC13-15 板载灯——彩灯常代替板载灯做
 * 指示，同框概率高；与声光件亦不叠），同选时经引脚绑定消解；页面默认
 * PB12 不采用——本批 ttp224 四脚 + DIP/GRAY 三重叠已占）。
 * 颜色值 = 0xRRGGBB；内部按 WS2812 数据手册的 GRB 发送序存缓冲（在
 * ws2812_set_color 里做 R/G 换位，日常写 0xFF0000 = 红即可）。
 * ⚠️ 页面缺陷清单（全部修正 + notes 记录 + 测试守卫防回潮）：
 * ① 延时循环 `for(k = 0; i < 0; i++);` 条件写反 ×4（L74/L83 原理示例 +
 * L225/L234 实现段——0 次迭代脉宽全丢，照抄灯不亮）→ 时序重写不采用；
 * ② `LedId > ledsCount`（L155）off-by-one 越界（LedId=8 写 LedsArray[24..26]）
 * → 修正 `>=`（越界忽略）；
 * ③ 时序按 12MHz 标注（L52/L280：NOP×5≈0.26-0.32us；@12MHz 机器周期 83ns）
 * 而本工程 72MHz——页面脉宽标注全部作废，按时序手册重写（位 1 = 高
 * delay_us(1)+低 0.25us；位 0 = 高 0.25us+低 delay_us(1)；0.25us@72MHz =
 * 18×__NOP()；位周期 ≈1.25us）；
 * ④ .h 声明 setLedCount/getLedCount/RGB_LED_Write1（L281-282/L289）无定义
 * （页面上游残留）→ 不声明不实现（实现 = 本模块 set_led_count/led_count/
 * refresh 对齐 API）。
 * 数据手册时序：1 码 = 高 580ns~1us 低 220~420ns；0 码 = 高 220~380ns
 * 低 580ns~1us；位周期约 1.25us（800kHz）。本实现用 delay 模块的
 * delay_us(1) + 0.25us 精确换算（18×NOP），若实测灯不亮再微调
 * ws2812_stm32.c 里两处延时（真机板级行为不属于编译级验证）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/control--ws2812-color-rgb-led.md
 * （立创 wiki 地阔星移植手册，代码按模块库规范改写：去掉 printf/main.c
 * 演示、函数名规范化、引脚宏参数化、延时走 delay 模块、页面坏循环/12MHz
 * 时序弃用、越界修正）。 */

#define WS2812_MAX 8 /* 支持的灯数上限（颜色缓冲槽位数，页面原值） */

#define WS2812_RED   0xFF0000u /* 红 */
#define WS2812_GREEN 0x00FF00u /* 绿 */
#define WS2812_BLUE  0x0000FFu /* 蓝 */
#define WS2812_BLACK 0x000000u /* 熄灭 */
#define WS2812_WHITE 0xFFFFFFu /* 白 */

/* ws2812_init：初始化（推挽输出配置 + 清空缓冲 + 复位电平）。
 * 选 ws2812 后生成工程可直接调用；不烧录灯带也安全（引脚悬空）。 */
void ws2812_init(void);

/* ws2812_set_led_count：设置实际灯数（≤ WS2812_MAX），只下发这么多灯
 * （页面声明无定义的 setLedCount 补齐）。 */
void ws2812_set_led_count(uint8_t count);

/* ws2812_led_count：查询当前灯数（页面声明无定义的 getLedCount 补齐）。 */
uint8_t ws2812_led_count(void);

/* ws2812_set_color：设置第 led_id 盏灯颜色（0xRRGGBB，越界忽略——页面
 * LedId > ledsCount 修正为 >=）。 */
void ws2812_set_color(uint8_t led_id, uint32_t color);

/* ws2812_set_rgb：三原色分别设置（等价 set_color 合成 0xRRGGBB）。 */
void ws2812_set_rgb(uint8_t led_id, uint8_t r, uint8_t g, uint8_t b);

/* ws2812_refresh：把颜色缓冲里的全部灯数据下发一遍（含 ≥280us 复位）。 */
void ws2812_refresh(void);

#endif /* WS2812_STM32_H */
