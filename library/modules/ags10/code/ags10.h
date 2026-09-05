#ifndef AGS10_H
#define AGS10_H

#include <stdint.h>

/* AGS10 有害气体传感器驱动（mspm0 纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，不必占硬件 I2C 外设），读取 TVOC 浓度（ppb）。
 * 引脚 = 母版 syscfg 实例 AGS10：SCL（输出，默认 PB18——与 DC_MOTOR BIN1/
 * MAX7219 CS 默认重叠，同选时经引脚绑定消解）/ SDA（双向，默认 PA14——与
 * DCC_100_PWM2/WS2812 IN/RC522 SCK 同脚）。SDA 方向运行时切换（写 = 输出，
 * 读 ACK/数据 = 输入），DL_GPIO_initDigitalOutput/Input 由本驱动调用。
 * 通信协议（AGS10 数据手册 + 立创页面）：器件地址 0x1A（写 0x34/读 0x35）；
 * 读 TVOC：写寄存器 0x00 → 读 5 字节回包 = 状态 + TVOC 24bit（data[1..3]）+
 * CRC（data[4]，CRC8 初值 0xFF/多项式 0x31——页面 Calc_CRC8 原式）；
 * 页面规格 I2C ≤15kHz 与页面代码时序（半周期 5us ≈ 100kHz）不一致——按
 * 页面代码实现，真机通信异常时按规格调慢半周期（见 ags10.c 注释）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--ags10-harmful-gas-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化、IIC 原语族静态化、页面返回值（TVOC 值与 1-4 错误码混用）
 * 收敛为出参 + 状态码、页面读地址重试条件写反缺陷按函数注释语义修正）。 */

#define AGS10_ADDR 0x1Au /* 7bit 地址（页面 0x34 写/0x35 读 = 0x1A<<1 | 0/1） */
#define AGS10_REG_TVOC 0x00u /* 读 TVOC 数据寄存器（页面写值） */
#define AGS10_RETRY_MAX 50u  /* 读地址应答重试上限（页面 ≤50×1ms） */

/* ags10_init：空实现占位——AGS10 无独立初始化序列（页面演示直接读；
 * 预热 ≥120s 期间读数起步，属器件特性，等待归调用方）。 */
void ags10_init(void);

/* ags10_read：读 TVOC 浓度（ppb；0-99999 量程，25℃/50%RH 典型精度 25% 读数，
 * 采样周期 ≥2s、预热 ≥120s）。
 * 返回 0 = 成功（voc_ppb 出参带回）；1 = 通信失败（写地址应答）；
 * 2 = 发送失败（寄存器字节应答）；3 = 等待超时（读地址 >50×1ms 无应答）；
 * 4 = CRC 校验失败（页面失败码语义——页面返回值与 TVOC 值混用已收敛为
 * 出参 + 状态，mlx90614 先例）。 */
uint8_t ags10_read(uint32_t *voc_ppb);

#endif /* AGS10_H */
