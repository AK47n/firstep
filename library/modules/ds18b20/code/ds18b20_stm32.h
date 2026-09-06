/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《DS18B20温度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ds18b20-temp-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef DS18B20_STM32_H
#define DS18B20_STM32_H

#include <stdint.h>

/* DS18B20 单总线温度传感器驱动（stm32，纯驱动切片，ADR 0009）：
 * - 1-Wire 单总线位时序：一根数据线双向（主机拉低 ≥480us 复位 → 从机应答 →
 *   0xCC 跳过 ROM + 0x44 转换 → 0xCC + 0xBE 读 2 字节温度寄存器）；
 * - 数据线方向运行时切换（DS18B20_DATA_OUT/IN，照 DHT11_DATA 先例），
 *   模块板自带 4.7k 上拉；空闲时总线保持高电平；
 * - 微秒/毫秒延时走库内 delay 模块，CPU 忙等位时序，不占 TIMER；
 * - 读数 12bit 默认分辨率，0.0625℃ 系数（负温补码）（页面原式）；
 * - 无应答/释放超时 → ds18b20_init 返回 1（0 = 检测到器件）；
 * - API 与 mspm0 版完全对齐（ds18b20_init/read_temp，同函数名/同语义/
 *   同返回码）。
 * 引脚 = pin_config.h 单源 DS18B20_GPIO/DS18B20_PIN（默认 **PB1**——与
 * MOTOR_B_DIR2（TB6612 B 相第二方向脚）默认重叠：测温与单电机方向不同框、
 * 同选概率最低；刻意不叠声光/传感站/总线环境件——测温+声光/环境站为常见
 * 搭配；单总线件与软 I2C 总线件（PA6/PA7）不共脚；页面默认 PB0 不采用
 * = MOTOR_B_DIR（母版 TB6612 B 相第一方向脚），同选经引脚绑定消解）。
 * 通信协议（页面资料 + DS18B20 数据手册）：复位 拉低 ≥480us（750us）→
 * 释放 15us → 转输入等应答低（60~240us 区间，200×1us 超时）→ 等释放高
 * （240×1us 超时）；命令 0xCC 跳过 ROM（单器件）/0x44 启动温度转换/0xBE
 * 读暂存器（温度寄存器 2 字节；第 9 字节 = CRC——页面只读 2 字节，按页面
 * 不加 CRC 校验）；分辨率开机默认 12 位 = 0.0625℃/LSB（未写 CONFIG 寄存器
 * ——按页面「不进行修改」，参数化范围外）；负温补码（int16 直乘 ±0.0625）；
 * 读位槽 = 拉低 2us → 释放 → 转输入 12us 采样 → 50us 尾部（64us，落页面
 * 60-70us 区间）；写位 1 = 低 2us+高 60us、写位 0 = 低 60us+高 2us（62us）。
 * ⚠️ 页面缺陷修正清单（全部 notes 记录 + 测试守卫防回潮）：
 *  ① **0x44 后无转换等待（主缺陷）**——12bit 最长 750ms，页面未等 →
 *     立即 Check+0xBE 读回上电默认 85℃ 或不稳定值；本件补
 *     DS18B20_CONVERT_MS 750 等待（mspm0 批 6 修正沿用）；
 *  ② .h 页外声明未实现复位函数（.c 无定义——链接错误风险）→ 剔除；
 *  ③ 页面注释串台（L51-66 三标题错位、L107「MLX90614」、L143 DQ_OUT
 *     注释相反）→ 不落/注释正确化（页面串台记录 notes）；
 *  ④ 位槽时间轴常量单源本头（源码不散写字面量）；
 *  ⑤ 读毕释放总线（init 与 read 尾部 DS18B20_DATA_OUT + DATA_SET(1)——驱动
 *     空闲高电平，mspm0 同款机制）；
 *  ⑥ 函数名规范化（页面 GetTemperture 拼写 → read_temp）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--ds18b20-temp-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化、引脚宏前缀化（页面 DQ_* → DS18B20_DATA_*）、延时走 delay
 * 模块）。 */

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
 * （test_module_ds18b20.py::test_ds18b20_stm32_bit_slot_timeline_guard）。 */

/* ds18b20_init：复位总线并检测器件（页面 DS18B20_Init/Check 语义）。
 * 返回 0 = 检测到器件、1 = 无应答/释放超时（短路/未接/未上电）。 */
uint8_t ds18b20_init(void);

/* ds18b20_read_temp：完成一次转换并读取温度（℃），0.0625 系数 12bit
 * 分辨率、±0.5℃ 精度、量程 -55~+125℃；负温按补码换算（页面原式）。
 * 转换耗时约 750ms（12bit），内部忙等阻塞（调用方按需节流——建议间隔
 * ≥1s：转换 + 器件自发热）。失败语义照 mspm0 .h：内部无应答时按读回数据
 * 换算返回（上次/默认值——页面语义；器件缺席由 ds18b20_init 报告）。 */
float ds18b20_read_temp(void);

#endif /* DS18B20_STM32_H */
