#ifndef MS5611_H
#define MS5611_H

#include <stdint.h>

/* MS5611-01BA03 高精度气压/温度传感器驱动（mspm0，纯驱动切片，ADR 0009）：
 * 软 I2C 位操作（SCL/SDA 两 GPIO，不必占硬件 I2C 外设——sht30/sgp30/bmp180
 * 先例，SDA 方向运行时切换），ms5611_init 封装页面 main 序列（复位 0x1E →
 * delay 300ms → Read_PROM 8 字 C1..C6+CRC——校准数据 init 缓存为模块静态）+
 * ms5611_read 出温度（℃，0.01℃ 分辨率——页面整数℃截断修正）与气压（Pa，
 * 0.01mbar == 1Pa——页面 /100 = hPa 统一为 Pa 修正）+ ms5611_read_altitude
 * 出海拔（米，44330 公式——与 bmp180 共用换算）。
 * 引脚 = 母版 syscfg 实例 MS5611：SCL（输出，默认 PA28）/ SDA（双向，默认
 * PA31——低频采集池（IMU601/FINGERPRINT_UART/HX711/SHT30/JY61P/MICROWAVE/
 * TP_XPT2046/OLED_SPI——姿态/称重/身份/温湿度/微波/显示，jy61p 同池先例；
 * MS5611 高精度件与姿态/飞行器定高同框概率最高——池内重叠、同选时经引脚
 * 绑定消解；刻意与互替件 bmp180 错开）；PA0/PA1 不可作软 I2C SDA——
 * 2026-09-06 SysConfig CLI 实证。
 * 通信协议（页面资料 + MS5611 数据手册）：器件地址 0xEE（写）/0xEF（读）
 * （CSB 高 = 1110 110；PS 上拉 = I2C 模式）；复位命令 0x1E；PROM 基址
 * 0xA0 + i*2（i=0..7：厂家信息 + C1..C6 + CRC）；转换命令 0x48 = D1 气压
 * （OSR 4096）/ 0x58 = D2 温度（OSR 4096，12 比特半位翻转后 0x00 读取）；
 * 换算（页面原式）：dT=D2−C5×256、TEMP=2000+dT×C6/2^23（0.01℃）、
 * OFF=C2×2^16+C4×dT/128、SENS=C1×2^15+C3×dT/256、P=(D1×SENS/2^21−OFF)/2^15
 * （0.01mbar == Pa）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--ms5611-pressure-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、IIC 原语静态化、main 序列封装 init、Get_pressure 重复调
 * Get_TEMP 合并、NACK printf 改码、全局收敛模块静态）。 */

#define MS5611_ADDR_W 0xEEu /* 器件地址+写（页面 0xee|0；CSB 高） */
#define MS5611_ADDR_R 0xEFu /* 器件地址+读（页面 0xee|1；CSB 高） */
#define MS5611_CMD_RESET 0x1Eu  /* 复位命令（页面 0x1e） */
#define MS5611_CMD_D1 0x48u     /* 气压转换命令 OSR=4096（页面 0x48） */
#define MS5611_CMD_D2 0x58u     /* 温度转换命令 OSR=4096（页面 0x58） */
#define MS5611_PROM_BASE 0xA0u  /* PROM 基址（页面 0xA0 + i*2，8 字） */
#define MS5611_PROM_WORDS 8u
#define MS5611_CONV_WAIT_MS 10u /* 转换等待（页面 10ms——命令/读取两段各一次） */
#define MS5611_INIT_WAIT_MS 300u /* 复位后等待初始化完成（页面 300ms） */

/* ms5611_init：页面 main 序列封装——复位 0x1E（返回 0 = 成功、1 = 器件
 * 地址错误、2 = 命令无应答——页面码）→ delay 300ms → Read_PROM 8 字
 * （0xA0..0xAE：C1..C6 = idx1..6 + CRC = idx7，页面原式；**页面 PROM 读的
 * I2C_WaitAck 无应答检查缺漏——人工复核修正：逐段检查应答并返回 3 = PROM
 * 读应答失败**，notes 记录）。 */
uint8_t ms5611_init(void);

/* ms5611_read：触发一次 D1/D2 转换并换算（页面 Get_TEMP 的 2 次转换按原式
 * + Get_pressure 换算合并——单次 D1/D2 读取 + 一次 dT/TEMP/OFF/SENS/P
 * 全换算，页面 Get_pressure 内嵌重复调 Get_TEMP 的二次重读省去，结果等价，
 * notes 记录）。返回 0 = 成功、1 = D1 段失败、2 = D2 段失败、3 = 数据读
 * 失败（读地址无应答——页面 NACK printf 改码，段内细分码保留内部）；
 * 成功后温度/气压经出参带回（℃ 0.01 分辨率——页面 Get_TEMP 整数℃截断
 * dat=(TEMP/1000)*10+(TEMP/100%10) 丢小数，人工复核修正保留；Pa——
 * P 单位 0.01mbar == 1Pa，页面 /100 = hPa，统一出 Pa；出参可传 NULL）。 */
uint8_t ms5611_read(float *temp_c, float *pressure_pa);

/* ms5611_read_altitude：气压→海拔换算（与 bmp180 共用 44330 公式——
 * math.h/pow，ir_distance 编译先例；两件分工见 manifest notes），p 单位 Pa，
 * 返回海拔米。 */
float ms5611_read_altitude(float pa);

#endif /* MS5611_H */
