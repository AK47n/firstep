#ifndef TCS34725_H
#define TCS34725_H

#include <stdint.h>

/* TCS34725 颜色识别传感器驱动（mspm0，纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，不必占硬件 I2C 外设，照 aht10 先例——IIC 原语静态化、
 * SDA 方向运行时切换、延时走 delay 模块），读 RGBC（红/绿/蓝/清光）16bit 原始
 * 值，积分时间（2.4ms~700ms）与增益（1X/4X/16X/60X）可配，RGB→HSL 换算保留
 * 页面原式。
 * 引脚 = 母版 syscfg 实例 TCS34725：SCL（输出，默认 PA23——与 HUIDU L2 /
 * UWB/DEBUG/HC05 UART TX / NRF24L01 CSN 默认重叠，同选时经引脚绑定消解）/
 * SDA（双向，默认 PA24——与 HUIDU L3 / UWB/HC05 UART RX / ADC12_0 MEM0
 * （adc+us016 共享槽）同脚）。SDA 方向运行时切换（写 = 输出，读 ACK/数据 =
 * 输入），DL_GPIO_initDigitalOutput/Input 由本驱动调用。
 * 通信协议（TCS34725 数据手册）：7 位器件地址 0x29（8 位 = 0x52），寄存器
 * 访问前带 COMMAND_BIT 0x80（自动递增）；读 = 写指针（命令字节）→ 重 start +
 * 地址+读 → 连续读（末字节 NACK）；ID 寄存器 0x12 = 0x44（TCS34725）/
 * 0x4D（TCS34727）；数据寄存器低字节在前。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--tcs34725-color-recognition-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 main.c 演示与 printf、
 * 函数名规范化（TCS34725_Init/GetRawData/GetChannelData → tcs34725_init/
 * read_rgb/get_channel_data）、全局 COLOR_RGBC rgb / COLOR_HSL hsl 收敛为出参、
 * IIC 原语静态化、引脚宏参数化、延时走 delay 模块。页面 Init 的
 * `if(id==0x4D | id==0x44)` 按位或写法（`==` 优先级高于 `|` 故语义等价但易
 * 误导）改为 `||`。页面演示注记「读两次，实际测试时发现读到的颜色总是上一次
 * 的颜色」系页面主循环未按 STATUS_AVALID 判定一次读全——本实现 GetRawData
 * 原判定保留（AVALID 置位才算新一轮数据）。 */

#define TCS34725_ADDR        (0x29u) /* 7 位器件地址（8 位 = 0x52/0x53） */
#define TCS34725_COMMAND_BIT (0x80u) /* 寄存器访问命令位（自动递增使能） */

/* 寄存器地址（页面寄存器族；数据寄存器低字节在前） */
#define TCS34725_ENABLE   (0x00u)
#define TCS34725_ATIME    (0x01u) /* 积分时间 */
#define TCS34725_STATUS   (0x13u)
#define TCS34725_ID       (0x12u) /* 0x44 = TCS34721/TCS34725、0x4D = TCS34723/TCS34727 */
#define TCS34725_CDATAL   (0x14u) /* Clear 通道数据（低字节） */
#define TCS34725_RDATAL   (0x16u) /* 红通道数据 */
#define TCS34725_GDATAL   (0x18u) /* 绿通道数据 */
#define TCS34725_BDATAL   (0x1Au) /* 蓝通道数据 */
#define TCS34725_CONTROL  (0x0Fu) /* 增益 */

#define TCS34725_ENABLE_PON (0x01u) /* 内部振荡器上电 */
#define TCS34725_ENABLE_AEN (0x02u) /* RGBC 转换使能 */

#define TCS34725_STATUS_AVALID (0x01u) /* RGBC 已完整积分一轮，数据有效 */

#define TCS34725_INTEGRATIONTIME_2_4MS (0xFFu)
#define TCS34725_INTEGRATIONTIME_24MS  (0xF6u) /* 页面默认（10 周期） */
#define TCS34725_INTEGRATIONTIME_50MS  (0xEBu)
#define TCS34725_INTEGRATIONTIME_101MS (0xD5u)
#define TCS34725_INTEGRATIONTIME_154MS (0xC0u)
#define TCS34725_INTEGRATIONTIME_240MS (0x9Cu)
#define TCS34725_INTEGRATIONTIME_700MS (0x00u)

#define TCS34725_GAIN_1X  (0x00u) /* 页面默认 */
#define TCS34725_GAIN_4X  (0x01u)
#define TCS34725_GAIN_16X (0x02u)
#define TCS34725_GAIN_60X (0x03u)

/* RGBC 原始值（页面 COLOR_RGBC 同款；c = Clear 全光通道） */
typedef struct {
    uint16_t c;
    uint16_t r;
    uint16_t g;
    uint16_t b;
} TCS34725_RGBC;

/* HSL 换算结果（页面 COLOR_HSL 同款：h [0,360]、s/l [0,100]） */
typedef struct {
    uint16_t h;
    uint8_t s;
    uint8_t l;
} TCS34725_HSL;

/* tcs34725_init：读 ID 判器件（0x44 = TCS34725 / 0x4D = TCS34727），成功则
 * 设积分时间 24ms + 增益 1X + Enable（PON|AEN）并返回 1；未检出返回 0
 * （页面 Init 同款——调用方按返回判定接线/供电问题）。 */
uint8_t tcs34725_init(void);

/* tcs34725_read_rgb：读 STATUS，AVALID 置位才算新一轮数据并读 C/R/G/B 各
 * 16bit 到出参；返回 1 = 数据已更新、0 = 未完成（调用方可延后重试，
 * 页面 GetRawData 语义）。 */
uint8_t tcs34725_read_rgb(TCS34725_RGBC *out);

/* tcs34725_rgb_to_hsl：RGBC → HSL 换算（页面 RGBtoHSL 原式——r/g/b 先按
 * Clear 通道标定到 [0,100] 再算 h [0,360]、s/l [0,100]；max3v/min3v 分别求
 * 大/小值：括号法无分支、无中间变量，与页面宏一致）。 */
void tcs34725_rgb_to_hsl(const TCS34725_RGBC *rgb, TCS34725_HSL *hsl);

/* tcs34725_set_integration_time：设积分时间（TCS34725_INTEGRATIONTIME_* 一档，
 * 寄存器 ATIME；调后需等待该时长才有新数据）。 */
void tcs34725_set_integration_time(uint8_t time_val);

/* tcs34725_set_gain：设增益（TCS34725_GAIN_* 一档，寄存器 CONTROL）。 */
void tcs34725_set_gain(uint8_t gain);

/* tcs34725_enable / tcs34725_disable：使能/失能（PON|AEN —— 页面 Enable 两段
 * 写：先 PON 后 PON|AEN；Disable 读回清掉 PON|AEN 再写）。 */
void tcs34725_enable(void);
void tcs34725_disable(void);

/* tcs34725_write_reg / tcs34725_read_reg：底层寄存器访问（subAddr 不带命令位，
 * 内部自动置 TCS34725_COMMAND_BIT；读 = 写指针 + 重 start + 读 n 字节，
 * 页面 TCS34725_Write/Read 同款）。 */
void tcs34725_write_reg(uint8_t sub_addr, const uint8_t *data, uint8_t n);
void tcs34725_read_reg(uint8_t sub_addr, uint8_t *data, uint8_t n);

#endif /* TCS34725_H */
