#ifndef BH1750_H
#define BH1750_H

#include <stdint.h>

/* BH1750 光照度驱动（mspm0 纯驱动，ADR 0009）：
 * - 软 I2C 位操作读取（不占硬件 I2C 外设，SDA 方向运行时切换，照 aht10）；
 *   器件地址 0x46（ALT ADDRESS 脚接地；接电源 = 0xB8，改 BH1750_ADDR 一处）；
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
