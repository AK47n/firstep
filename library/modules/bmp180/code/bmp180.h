/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《BMP180气压传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/bmp180-pressure-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef BMP180_H
#define BMP180_H

#include <stdint.h>

/* BMP180 气压/温度/海拔传感器驱动（mspm0，纯驱动切片，ADR 0009）：软 I2C
 * 位操作（SCL/SDA 两 GPIO，不必占硬件 I2C 外设——sht30/sgp30 先例，SDA
 * 方向运行时切换），bmp180_init 读 11 项出厂校准系数（页面 BMP180_Get_param
 * 序列入 init——校准数据是每次读数的必需输入，init 缓存为模块静态，
 * sgp30_init 先例）+ bmp180_read 出温度（℃）/气压（Pa）（页面
 * Get_Temperature + Get_Pressure **原式合并**——气压段复用 B5，页面
 * Get_Pressure 内嵌重复调 Get_Temperature 的二次读取省去，结果等价）+
 * bmp180_read_altitude 出海拔（米，页面 44330 公式）。
 * 引脚 = 母版 syscfg 实例 BMP180：SCL（输出，默认 PA23）/ SDA（双向，默认
 * PA24——与 HUIDU L2/L3（巡线）、UWB/HC05 链路、NRF24L01 CSN/MOSI、
 * TCS34725 SCL/SDA、ADC12_0 adcPin3 重叠：气压/海拔与巡线车控/无线链路/
 * 色觉不同框、同选概率最低（刻意不叠温湿度/光照/气体等环境件与显示/语音
 * ——气压+环境站/显示为常见搭配；与互替件 ms5611 刻意错开），同选时经引脚
 * 绑定消解；PA0/PA1 不可作软 I2C SDA——2026-09-06 SysConfig CLI 实证）。
 * 通信协议（页面资料 + BMP180 数据手册）：器件地址 0xEE（写）/0xEF（读）；
 * 命令寄存器 0xF4——温度 0x2E、气压 0x34+(oss<<6)（本件固定 oss=0 =
 * ultra low power 页面默认，参数化范围外）；校准系数地址 0xAA..0xBE
 * （AC1..MD 共 11 项，高八位在 MSB 地址）；温度换算 T=((B5+8)/16.0)*0.1
 * （每数值 0.1℃）、气压换算页面全套原式（单位 Pa）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--bmp180-pressure-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、IIC 原语静态化、校准读取封装 init、全局收敛模块静态、NACK
 * printf 改状态码返回）。 */

#define BMP180_ADDR_W 0xEEu /* 器件地址+写（页面 0XEE） */
#define BMP180_ADDR_R 0xEFu /* 器件地址+读（页面 0XEF） */
#define BMP180_REG_CTRL_MEAS 0xF4u /* 命令寄存器（页面 0xf4） */
#define BMP180_CMD_TEMP 0x2Eu      /* 温度读取命令（页面 0x2E） */
#define BMP180_CMD_PRES 0x34u      /* 气压读取命令 oss=0（页面 0x34） */
#define BMP180_OSS 0u /* 工作模式：固定 0 = ultra low power（页面默认，参数化范围外） */

/* bmp180_init：读 11 项出厂校准系数（页面 BMP180_Get_param 序列原式：
 * 0xAA..0xBE 逐项 Read16 入模块静态——AC1..MD；校准数据是每次读数的
 * 必需输入，init 缓存为静态。返回 0 = 成功、1 = 校准读取段失败。 */
uint8_t bmp180_init(void);

/* bmp180_read：触发一次完整读取（页面 Get_Temperature + Get_Pressure
 * 原式合并——温度段 0xF4←0x2E→delay 6ms→读 0xF6 2 字节→X1/X2/B5/T，
 * 气压段 0xF4←0x34+(oss<<6)→delay 10ms→读 0xF6 3 字节→B6..B7/p 全套）。
 * 返回 0 = 成功、1 = 温度段失败、2 = 气压段失败（段内细分码
 * 写地址/命令/读地址超时 5×1ms 保留在底层，段级映射 sht20 先例）；
 * 成功后温度/气压经出参带回（℃ / Pa，页面「T 每数值 0.1℃、p 每数值
 * 1Pa」；出参可传 NULL——只取一路）。 */
uint8_t bmp180_read(float *temp_c, float *pa);

/* bmp180_read_altitude：气压→海拔换算（页面原式 44330×(1-pow(p/101325,
 * 1/5.255))，math.h/pow——ir_distance 编译先例），p 单位 Pa，返回海拔米。 */
float bmp180_read_altitude(float pa);

#endif /* BMP180_H */
