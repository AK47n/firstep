#ifndef SGP30_H
#define SGP30_H

#include <stdint.h>

/* SGP30 空气质量传感器驱动（mspm0 纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，不必占硬件 I2C 外设），读取 TVOC（总挥发性有机物，
 * ppb）与 CO2 当量（ppm）。
 * 引脚 = 母版 syscfg 实例 SGP30：SCL（输出，默认 PA18——与 DC_MOTOR AIN2/
 * MAX7219 CLK/RC522 RST 默认重叠，同选时经引脚绑定消解）/ SDA（双向，
 * 默认 PB9——与 DC_MOTOR AIN1/MAX7219 DIN 同脚）。SDA 方向运行时切换
 * （写 = 输出，读 ACK/数据 = 输入），DL_GPIO_initDigitalOutput/Input 由
 * 本驱动调用。
 * 通信协议（SGP30 数据手册 + 立创页面）：器件地址 0x58（写 0xB0/读 0xB1）；
 * 初始化命令 0x2003（init_air_quality，空气特征值/基准）；测量命令 0x2008
 * （measure_air_quality）——页面写命令内嵌 delay_ms(100) 覆盖器件测量时长；
 * 回包 6 字节 = CO2 高/低 + CRC + TVOC 高/低 + CRC，CRC8（多项式 0x31、初值
 * 0xFF——同 SHT30/AGS10 系）两组校验（页面实现缺 CRC 校验且只读 5 字节漏
 * TVOC CRC 字节，按数据手册修正——器件正确性修正，非页面语义变化）。
 * 上电需 15s 左右预热：预热期 CO2=400ppm、TVOC=0ppb 恒定，读到 TVOC≠0 且
 * CO2≠400 才算初始化完成（判定归生成骨架/调用方循环）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--sgp30-gas-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化、IIC 原语静态化、延时走 delay 模块、打包值 uint32_t 收敛为
 * 双出参 + 状态码）。 */

#define SGP30_ADDR              0x58u /* 7bit 地址（页面 0x58<<1=0xB0 写/读 0xB1） */
#define SGP30_CMD_INIT_AIR      0x2003u /* init_air_quality：初始化空气特征基准 */
#define SGP30_CMD_MEASURE_AIR   0x2008u /* measure_air_quality：读取空气质量值 */

/* sgp30_init：发送 0x2003 初始化空气特征值/基准（页面 SGP30_Init 语义）；
 * 上电预热 15s 左右，预热判定（TVOC≠0 且 CO2≠400）归调用方循环。 */
void sgp30_init(void);

/* sgp30_read：发 0x2008 测量命令（写命令内嵌延时覆盖器件测量时长）+ 读
 * 6 字节回包 + CRC8 两组校验，TVOC/CO2 经出参带回（ppb / ppm）。
 * 返回 0 = 成功；1 = 写命令应答失败（页面原式无应答检查，按 sht30 风格补）；
 * 2 = 读地址应答失败；3 = CRC 校验失败（器件正确性修正——页面缺校验）。 */
uint8_t sgp30_read(uint16_t *tvoc_ppb, uint16_t *co2_ppm);

#endif /* SGP30_H */
