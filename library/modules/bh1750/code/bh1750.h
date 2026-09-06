/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《BH1750光照强度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/bh1750-light-intensity-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef BH1750_H
#define BH1750_H

#include <stdint.h>

/* BH1750 光照度驱动（mspm0 纯驱动，ADR 0009）：
 * - 软 I2C 位操作读取（不占硬件 I2C 外设，SDA 方向运行时切换，照 aht10）；
 *   器件地址 0x46（ALT ADDRESS 脚接地；接电源 = 0xB8，改 BH1750_ADDR_WRITE
 *   一处）；
 * - 一次测量：bh1750_init（Power On）→ bh1750_start_measure（0x10 连续
 *   高分辨率）→ 等 ≥BH1750_MEASURE_DELAY_MS → bh1750_read_lux；
 * - 光照度 = 高 8 位 << 8 | 低 8 位，除以 1.2 出 lx（0-65535 lx，1 lx 分辨率）。 */

#define BH1750_MEASURE_DELAY_MS 140 /* 连续高分辨率测量周期 ≥120ms（手册推荐） */

void bh1750_init(void);
/* 启动连续高分辨率测量（0x10）；返回 0=成功 1=无应答（器件上电/接线错误） */
uint8_t bh1750_start_measure(void);
/* 读取 2 字节并换算 lx（调用前须等 ≥BH1750_MEASURE_DELAY_MS）；
 * 返回 0=成功 1=无应答；出参失败时保持原值 */
uint8_t bh1750_read_lux(float *lux);

#endif /* BH1750_H */
