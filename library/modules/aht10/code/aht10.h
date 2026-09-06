/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AHT10温湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/aht10-temp-humi-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef AHT10_H
#define AHT10_H

#include <stdint.h>

/* AHT10 温湿度传感器驱动（mspm0，纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，不必占硬件 I2C 外设），读取温湿度并按换算公式出摄氏
 * 度 / 百分比相对湿度。
 * 引脚 = 母版 syscfg 实例 AHT10：SCL（输出，默认 PA26——与 ZIGBEE_UART RX/
 * HUIDU R1 默认重叠，同选时经引脚绑定消解）/ SDA（双向，默认 PA25——与
 * ZIGBEE_UART TX/HUIDU L4 同脚）。SDA 方向运行时切换（写 = 输出，读 ACK/
 * 数据 = 输入），DL_GPIO_initDigitalOutput/Input 由本驱动调用，SysConfig
 * 侧仅做端口时钟与初始输出电平。
 * 通信协议（AHT10 数据手册）：器件地址 0x38，先发校准命令（0xE1 0x08 0x00），
 * 再发触发测量（0xAC 0x33 0x00），间隔 ≥80ms 后读 6 字节（状态 + 湿度 20 位
 * + 温度 20 位）。换算：湿度 = data/2^20*100；温度 = data/2^20*200-50。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--aht10-temp-humi-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 main.c 演示与 printf、
 * 函数名规范化、引脚宏参数化、延时走 delay 模块、GLOBAL 温湿度缓存改传参）。 */

/* aht10_init：软复位 + 校准（等待 50ms 稳定 + 发校准命令）。 */
void aht10_init(void);

/* aht10_read：触发一次测量并读取，返回 0 = 成功、1 = 超时/无应答；
 * 成功后温度/湿度经出参带回（单位 ℃ / %RH）。 */
uint8_t aht10_read(float *temperature_c, float *humidity_rh);

/* aht10_read_temperature：读取温度（℃）；内部自动完成一次测量。 */
float aht10_read_temperature(void);

/* aht10_read_humidity：读取相对湿度（%RH）；内部自动完成一次测量。 */
float aht10_read_humidity(void);

#endif /* AHT10_H */
