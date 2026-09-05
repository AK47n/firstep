#ifndef DS18B20_H
#define DS18B20_H

#include <stdint.h>

/* DS18B20 单总线温度驱动（mspm0 纯驱动，ADR 0009）：
 * - 1-Wire 单总线位时序：一根数据线双向（主机拉低 ≥480us 复位 → 从机应答 →
 *   0xCC 跳过 ROM + 0x44 转换 → 0xCC + 0xBE 读 2 字节温度寄存器）；
 * - 数据线方向运行时切换（DS18B20_DATA_OUT/IN，照 DHT11_DATA 先例），
 *   模块板自带 4.7k 上拉；空闲时总线保持高电平；
 * - 微秒/毫秒延时走库内 delay 模块，CPU 忙等位时序，不占 TIMER；
 * - 读数 12bit 默认分辨率，0.0625℃ 系数（负温补码）（页面原式）；
 * - 无应答/释放超时 → ds18b20_init 返回 1（0 = 检测到器件）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--ds18b20-temp-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、引脚宏参数化、延时走 delay 模块；页面头文件额外声明了一个未实现
 * 的复位函数（上游缺陷）——已剔除，见 manifest notes；页面仅读温度 2 字节、
 * 不读第 9 字节 CRC，按页面不加 CRC 校验）。 */

/* ---------- 位槽时间轴（页面原值；源码只引用常量，不散写字面量） ---------- */

#define DS18B20_T_RESET_LOW_US     750u /* 复位：拉低 ≥480us（页面 750us） */
#define DS18B20_T_RESET_RECOVER_US 15u  /* 复位：释放后等待（页面 15us） */
#define DS18B20_T_RESET_TIMEOUT    200u /* 应答等待超时步进数（1us/步，页面原值） */
#define DS18B20_T_RELEASE_TIMEOUT  240u /* 释放等待超时步进数（1us/步，页面原值） */

#define DS18B20_T_WRITE_START_US   2u   /* 写位槽：起始拉低（页面原值） */
#define DS18B20_T_WRITE_HIGH_US    60u  /* 写位 1：释放高电平持续（页面原值） */
#define DS18B20_T_WRITE_LOW_US     60u  /* 写位 0：拉低持续（页面原值） */
#define DS18B20_T_WRITE_END_US     2u   /* 写位 0：释放后等待（页面原值） */

#define DS18B20_T_READ_START_US    2u   /* 读位槽：起始拉低（页面原值） */
#define DS18B20_T_READ_SAMPLE_US   12u  /* 读位槽：转输入后采样点（页面原值） */
#define DS18B20_T_READ_HOLD_US     50u  /* 读位槽：采样后尾部（页面原值） */

#define DS18B20_TEMP_SCALE 0.0625f /* 12bit 分辨率系数（±0.5℃ 精度） */

#define DS18B20_CONVERT_MS  750u  /* 12bit 最大转换时间（数据手册；页面
                                   * GetTemperture 未等待转换完成——首次读回
                                   * 上电默认 85℃ 或不稳定值，本实现按手册等待，
                                   * 改动见 manifest notes） */

/* 位槽时间轴（页面原值；源码只引用常量，不散写字面量）：
 * 读位槽 = 起始 2us + 采样点 12us + 尾部 50us = 64us；写位槽 = 2+60 / 60+2
 * = 62us——全落页面 60-70us 位槽区间。测试侧按常量计算钉死该时间轴
 * （test_module_ds18b20.py::test_ds18b20_bit_slot_timeline_guard）。 */

/* ds18b20_init：复位总线并检测器件（页面 DS18B20_Init/Check 语义）。
 * 返回 0 = 检测到器件、1 = 无应答/释放超时（短路/未接/未上电）。 */
uint8_t ds18b20_init(void);

/* ds18b20_read_temp：完成一次转换并读取温度（℃），0.0625 系数 12bit
 * 分辨率、±0.5℃ 精度、量程 -55~+125℃；负温按补码换算（页面原式）。
 * 转换耗时约 750ms（12bit），内部忙等阻塞（调用方按需节流）。 */
float ds18b20_read_temp(void);

#endif /* DS18B20_H */
