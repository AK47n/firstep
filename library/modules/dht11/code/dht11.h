#ifndef DHT11_H
#define DHT11_H

#include <stdint.h>

/* DHT11 数字温湿度驱动（mspm0 纯驱动，ADR 0009）：
 * - 单总线位时序：一根数据线双向（主机拉低 ≥18ms 起始 → 模块响应 →
 *   40bit 数据（高位先出）→ 校验和；位 0/1 按高电平时长区分）；
 * - 数据线方向运行时切换（DHT11_DATA_OUT/IN，照 AHT10_SDA 先例），
 *   模块板自带上拉；空闲时总线保持高电平；
 * - 微秒/毫秒延时走库内 delay 模块，CPU 忙等位时序，不占 TIMER；
 * - 校验和失败或应答超时 → dht11_read 返回 1（0 = 成功）。 */

void dht11_init(void);
/* 一次完整测量：内部完成起始/响应/40bit 接收/校验/换算。
 * 出参 temperature_c（℃）/ humidity_rh（%RH）；返回 0=成功 1=失败
 * （校验和不符或应答超时——出参保持上次值不变）。 */
uint8_t dht11_read(float *temperature_c, float *humidity_rh);
float dht11_read_temperature(void); /* 便捷封装（失败返回上次值） */
float dht11_read_humidity(void);    /* 便捷封装（失败返回上次值） */

#endif /* DHT11_H */
