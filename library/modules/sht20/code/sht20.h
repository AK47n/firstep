#ifndef SHT20_H
#define SHT20_H

#include <stdint.h>

/* SHT20 温湿度传感器驱动（mspm0，纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，不占硬件 I2C 外设/TIMER），单次测量模式（no-hold，
 * 低功耗），读取温湿度并按页面换算公式出摄氏度 / 百分比相对湿度。
 * 引脚 = 母版 syscfg 实例 SHT20：SCL（输出，默认 PA16——与 DC_MOTOR 编码器
 * AA/RC522 MOSI/ADS1115 SCL 默认重叠，同选时经引脚绑定消解）/ SDA（双向，
 * 默认 PA17——与编码器 AB/RC522 MISO/ADS1115 SDA 同脚）。SDA 方向运行时
 * 切换（写 = 输出，读 ACK/数据 = 输入），DL_GPIO_initDigitalOutput/Input
 * 由本驱动调用。
 * 通信协议（SHT2x 数据手册 + 立创页面）：器件地址 0x40（写 0x80/读 0x81）；
 * 测量命令 0xF3 = 温度 no-hold 单次 / 0xF5 = 湿度 no-hold 单次（低功耗单次
 * 测量——与 sht30 周期模式 0x2130 分工）；最长测量 85ms（温度 14bit）/
 * 29ms（湿度 12bit）；回包 2 字节（14bit 左对齐 + 低 2 位状态位——物理计算
 * 前 & 0xFFFC 置 0，页面正文要求但页面代码未掩码，本驱动按手册修正）；
 * 页面无 CRC（「校验和可以不需要」——数据后发 NACK，照页面取舍）。
 * 换算（页面原式，0.01 系数口径）：温度 = raw/65536×175.72−46.85、
 * 湿度 = raw/65536×125−6。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--sht20-temp-humi-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * SHT20_Read 按库风格重命名 sht20_read、IIC 原语静态化、延时走 delay 模块；
 * 页面 do-while 裸轮询（~50us/次）改 ≤50×2ms 重试——页面 85ms 最长测量
 * 需 100ms 覆盖，notes 记录）。 */

#define SHT20_ADDR           0x40u /* SHT2x 固定地址（页面原式 0x80 写/0x81 读） */
#define SHT20_CMD_TEMP       0xF3u /* 温度测量（no-hold 单次，低功耗模式） */
#define SHT20_CMD_HUMI       0xF5u /* 湿度测量（no-hold 单次，低功耗模式） */
#define SHT20_READ_RETRY_MAX 50u   /* 读地址应答重试上限（页面最长测量 85ms，
                                    * ≤2ms×50 = 100ms 覆盖） */
#define SHT20_READ_RETRY_MS  2u

/* sht20_init：无器件初始化序列（单次测量模式无预置命令——页面 bsp 无 init，
 * SYSCFG_DL_init() 已配置引脚），空实现占位。 */
void sht20_init(void);

/* sht20_read：完整读取温度 + 湿度两段（各 = 写地址 → 写测量命令 → 轮询读
 * 地址应答直到测量完成 → 读 2 字节 → NACK + 停止），返回 0 = 成功（出参
 * 有效：°C / %RH，分辨率 0.01 级——页面 ±0.3℃/±3%RH 精度档）、1 = 温度段
 * 测量失败（写地址/测量命令应答失败或读地址应答超时——页面 85ms 最长测量
 * 超出 100ms 重试窗口）、2 = 湿度段测量失败（同上；失败时出参不变）。 */
uint8_t sht20_read(float *temperature_c, float *humidity_rh);

#endif /* SHT20_H */
