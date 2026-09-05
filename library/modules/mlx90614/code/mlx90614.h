#ifndef MLX90614_H
#define MLX90614_H

#include <stdint.h>

/* MLX90614 非接触红外测温传感器驱动（mspm0，纯驱动切片，ADR 0009）：软 I2C
 * （SMBus 兼容，SCL/SDA 两 GPIO，不必占硬件 I2C 外设，照 aht10 先例——IIC
 * 原语静态化、SDA 方向运行时切换、延时走 delay 模块），读被测目标温度
 * （REG_OBJECT_TEMP 0x07）与环境温度（REG_AMBIENT_TEMP 0x06），换算
 * ℃ = RAW × 0.02 − 273.15（页面公式：0.02K/LSB，内部数据 0.01℃ 分辨率，
 * 页面用 0.02 系数出整数步进）。
 * 引脚 = 母版 syscfg 实例 MLX90614：SCL（输出，默认 PA9——与 DIGIT_UART RX /
 * JOYSTICK SW / NRF24L01 MISO 默认重叠，同选时经引脚绑定消解）/ SDA（双向，
 * 默认 PA8——与 DIGIT_UART TX / IR_BEAM OUT / HC05 STATE 同脚）。SDA 方向
 * 运行时切换（写 = 输出，读 ACK/数据 = 输入），DL_GPIO_initDigitalOutput/
 * Input 由本驱动调用。
 * 通信协议（MLX90614 SMBus / 立创移植手册）：器件地址 0x5A（默认，7 位），
 * 8 位写/读 = 0xB4/0xB5（页面「0xB4 为器件地址左移一位后的值」）；命令字节
 * = bit7-5（RAM=000/EEPROM=001）+ bit4-0（RAM 单位地址仅低 5 位有效，Ta=0x06、
 * To=0x07）；读=写命令（地址+写，ACK）→ 重 start + 地址+读（ACK）→ 低 8 位
 * （ACK）+ 高 8 位（NACK）→ 停止；页面无重复起始后的延时（页面原 delay_ms(1)
 * 已注释）。页面 PEC_Calculation（CRC-8，多项式 X8+X2+X1+1）整体注释未启用
 * ——本实现不含 PEC（页面演示即不校验通路，真机验证留后续）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--mlx90614-non-contact-temp-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 main.c 演示与
 * printf、函数名规范化（MLX90614_Read(SlaveAddr, RegAddr) → mlx90614_read_word
 * 静态 + read_object_temp/read_ambient_temp 服务函数）、IIC 原语静态化、引脚
 * 宏参数化、延时走 delay 模块。**页面失败语义修正**：页面失败 `return 0.0`
 * 与合法 0.0℃ 混淆——本实现改出参 + 状态（0=成功 1=失败），notes 记录。
 * 页面函数注释名「MLX90615_Read」系笔误（函数名与器件均为 MLX90614）。 */

#define MLX90614_ADDR  0x5A /* 7 位器件地址（默认；8 位写/读 = 0xB4/0xB5） */
#define MLX90614_REG_AMBIENT_TEMP 0x06 /* RAM 环境温度 Ta */
#define MLX90614_REG_OBJECT_TEMP  0x07 /* RAM 被测目标温度 To */

/* mlx90614_init：SMBus 器件无上电初始化序列（出厂校验/线性化完成），空实现
 * 占位保持模块 API 一致（页面演示也无初始化）；校验是否在线由读温度判。 */
void mlx90614_init(void);

/* mlx90614_read_object_temp：读被测目标温度（寄存器 0x07），成功经出参带回
 * ℃（换算 RAW×0.02−273.15，页面公式）并返回 0；通信失败（无应答/超时）
 * 返回 1、出参不变。 */
uint8_t mlx90614_read_object_temp(float *temp_c);

/* mlx90614_read_ambient_temp：读环境温度（寄存器 0x06），语义同上。 */
uint8_t mlx90614_read_ambient_temp(float *temp_c);

#endif /* MLX90614_H */
