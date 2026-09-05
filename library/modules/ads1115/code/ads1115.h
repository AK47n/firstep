#ifndef ADS1115_H
#define ADS1115_H

#include <stdint.h>

/* ADS1115 四通道 16bit 外扩 ADC 驱动（mspm0，纯驱动切片，ADR 0009）：软 I2C
 * 位操作（SCL/SDA 两 GPIO，不必占硬件 I2C 外设，照 aht10 先例——IIC 原语
 * 静态化、SDA 方向运行时切换、延时走 delay 模块），读 16bit 有符号原始值 /
 * 换算电压，MUX 通道选择（AIN0-3）/增益（PGA）/数据率（DR）可配。
 * 引脚 = 母版 syscfg 实例 ADS1115：SCL（输出，默认 PA16——与 DC_MOTOR 编码器
 * AA / RC522 MOSI 默认重叠，同选时经引脚绑定消解）/ SDA（双向，默认 PA17——
 * 与 DC_MOTOR 编码器 AB / RC522 MISO 同脚）。SDA 方向运行时切换（写 = 输出，
 * 读 ACK/数据 = 输入），DL_GPIO_initDigitalOutput/Input 由本驱动调用。
 * 与库内 adc 模块（板载 12bit）分工：adc = 板载 ADC12_0 单通道轮询（默认
 * PA24，us016 共读同槽），ads1115 = I2C 外挂 4 通道 16bit（分辨率 15bit+符号，
 * 独立于板载 ADC/排针模拟量，多路模拟量分离供电场景）；多路采集用 ads1115、
 * 单路板载用 adc，二者可同时选中不冲突（不同总线/引脚）。
 * 通信协议（ADS1115 数据手册）：器件地址 0x48（ADDR 接地，7 位），8 位写/读
 * = 0x90/0x91；寄存器指针：0x00 = 转换结果（16bit 补码）、0x01 = 配置寄存器
 * （OS / MUX / PGA / MODE / DR / 比较器，页面最终配置 0xC283 = AIN0 单端 +
 * ±4.096V + 连续 128SPS + 比较器关）；读取 = 写指针 + 重 start + 地址+读 +
 * 高 8 位（ACK）+ 低 8 位（NACK）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--ads1115-multichannel-a-to-d-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 main.c 演示与
 * printf、函数名规范化、IIC 原语静态化、引脚宏参数化、延时走 delay 模块、
 * 页面负数电压换算缺陷修正（见下）。页面电压负数分支 `(65535-num)*0.000125`
 * 与 `num>32768`（未含 32768）系上游缺陷——本实现按 int16_t 补码正确换算
 * `raw/32768*FSR`；页面 `0.000125 = 4.096/2^15` 分辨率式正确。页面 do-while
 * 读重试（≤20 次 ×1ms，从机忙时不响应）保留。页面比较器阈值寄存器
 * Lo_thresh/Hi_thresh 与 ALERT/RDY 未用，不实现。 */

#define ADS1115_ADDR_DEFAULT 0x90 /* 器件地址 0x48 << 1（ADDR 接地；A0/A1 可选
                                   * 地址：ADDR=VDD→0x49、=SDA→0x4A、=SCL→0x4B，
                                   * 用 ads1115_set_address 切换） */
#define ADS1115_REG_CONVERSION 0x00 /* 转换结果寄存器（16bit 补码） */
#define ADS1115_REG_CONFIG    0x01 /* 配置寄存器（16bit） */

/* 配置寄存器位域（页面寄存器说明）：
 * bit15  OS      —— 读 = 转换状态；写 1 = 单次转换触发（单次模式）
 * bit14-12 MUX   —— 输入选择：AIN0-3 单端 = 0x04+ch（差分 0-1 = 0x00 等）
 * bit11-9 PGA    —— 满量程（见 ADS1115_PGA_*）
 * bit8   MODE    —— 0 = 连续转换、1 = 单次（页面配置连续模式）
 * bit7-5 DR      —— 数据率（见 ADS1115_DR_*）
 * bit4-2 比较器  —— 页面不用，0
 * bit1-0 比较器极性/锁存 —— 0x03（关闭比较器 + ALERT 高阻）
 * 页面最终配置 0xC283 = 1100 0010 1000 0011（OS=1、MUX=100(AIN0)、PGA=010
 * (±4.096V)、MODE=0(连续)、DR=100(128SPS)、比较器关）。 */
#define ADS1115_CONFIG_MUX_MASK 0x7000u
#define ADS1115_CONFIG_PGA_MASK 0x0E00u
#define ADS1115_CONFIG_DR_MASK  0x00E0u

#define ADS1115_PGA_6_144V 0x00u /* ±6.144V（FSR = 6.144） */
#define ADS1115_PGA_4_096V 0x01u /* ±4.096V（页面默认） */
#define ADS1115_PGA_2_048V 0x02u
#define ADS1115_PGA_1_024V 0x03u
#define ADS1115_PGA_0_512V 0x04u
#define ADS1115_PGA_0_256V 0x05u

#define ADS1115_DR_8SPS   0x00u
#define ADS1115_DR_16SPS  0x01u
#define ADS1115_DR_32SPS  0x02u
#define ADS1115_DR_64SPS  0x03u
#define ADS1115_DR_128SPS 0x04u /* 页面默认 */
#define ADS1115_DR_250SPS 0x05u
#define ADS1115_DR_475SPS 0x06u
#define ADS1115_DR_860SPS 0x07u

#define ADS1115_DEFAULT_CONFIG 0xC283u /* 页面最终配置（AIN0 单端 + ±4.096V +
                                       * 连续 128SPS + 比较器关） */

/* ads1115_init：写默认配置（ADS1115_DEFAULT_CONFIG），此后 ads1115_read 默认
 * 读 AIN0；无返回值（失败经 ads1115_read 返回 0 体现）。 */
void ads1115_init(void);

/* ads1115_write_register：页面 WriteADS1115 原式——向任意寄存器写 2 字节
 * （起始 → 地址+写 → 寄存器地址 → 高 8 位 → 低 8 位 → 停止）；
 * 返回 0 = 成功、1 = 器件地址无应答、2 = 寄存器地址无应答（页面同款；
 * 高/低字节无应答页面忽略，本实现同）。 */
uint8_t ads1115_write_register(uint8_t reg, uint8_t dat_hi, uint8_t dat_lo);

/* ads1115_write_config：写配置寄存器（0x01）并缓存；返回值语义同上。
 * 改变增益/数据率用 ads1115_set_gain/set_data_rate。 */
uint8_t ads1115_write_config(uint16_t config);

/* ads1115_read：切换 MUX 到通道 ch（0-3 = AIN0-3 单端）→ 读转换寄存器，
 * 返回 16bit 有符号原始值（补码；失败/重试 20 次超时返回 0——转换寄存器
 * 保持上次值，连续模式失败极罕见）。 */
int16_t ads1115_read(uint8_t ch);

/* ads1115_read_voltage：读通道 ch 并换算电压（V）= 原始值 / 32768 × FSR，
 * 按当前 PGA 增益；成功返回电压、失败返回 0.0。 */
float ads1115_read_voltage(uint8_t ch);

/* ads1115_set_gain：设 PGA 满量程（ADS1115_PGA_* 一档）并写入配置；
 * 返回 0 = 成功、非 0 = 写入无应答（页面语义）。增益档位与电压换算共用
 * 内表，参数不合法返回 1。 */
uint8_t ads1115_set_gain(uint8_t pga_idx);

/* ads1115_set_data_rate：设数据率（ADS1115_DR_* 一档）并写入配置；
 * 返回 0 = 成功、非 0 = 写入无应答/参数不合法。 */
uint8_t ads1115_set_data_rate(uint8_t dr_idx);

/* ads1115_set_address：改器件地址（7 位，如 0x48/0x49/0x4A/0x4B——A0/A1 可选，
 * 页面地址表；默认 0x48 无需调用），后续读写全部走新地址。 */
void ads1115_set_address(uint8_t addr7);

#endif /* ADS1115_H */
