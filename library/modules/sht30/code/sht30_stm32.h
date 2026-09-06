/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《SHT30温湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/sht30-temp-humi-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef SHT30_STM32_H
#define SHT30_STM32_H

#include <stdint.h>

/* SHT30 温湿度传感器驱动（stm32，纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设/TIMER），
 * 周期测量模式读取温湿度并按换算公式出摄氏度 / 百分比相对湿度。API 与
 * mspm0 版完全对齐（sht30_init/read/read_temperature/read_humidity，
 * 同函数名/同语义/同返回码）。
 * 引脚 = pin_config.h 单源 SHT30_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——与 motor MOTOR_A_DIR/DIR2 默认重叠：温湿度与「带电机
 * 方向的小车运动控制」不同框、同选概率最低；**六件软 I2C 件默认共挂此总线**
 * （地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异——环境站合法共挂；页面默认
 * SDA=PB8/SCL=PB9 不采用 = 母版 OLED 段），同选时经引脚绑定消解。
 * 通信协议（SHT30 数据手册 + 立创页面）：器件地址 0x44（ADDR 接地，写
 * 0x88/读 0x89）；周期测量模式命令 0x2130（每秒 1 次高重复性）；读命令
 * 0xE000（周期模式读）；6 字节回包 = 温度高/低 + CRC + 湿度高/低 + CRC，
 * CRC8（多项式 0x31、初值 0xFF）两组校验；换算（页面 0.01 系数）：
 * 温度 = data/65535×175−45、湿度 = data/65535×100。
 * ⚠️ 页面缺陷修正清单（全部 notes 记录 + 测试守卫防回潮）：
 *  ① 串台文案：页面 L44「ADS1115是采用的IIC通信」（ADS1115 页残留）——
 *     本实现不落；
 *  ② 页外 extern 泄漏：页面 .h `extern double Temperature, Humidity;`
 *     （全批唯一）→ float 出参 + static 收敛（mspm0 版已同）；
 *  ③ 命令表 0x2126（1 次/s 中重复）vs 代码 0x2130（1 次/s 高重复）——两值
 *     皆合法（手册），采信代码 0x2130，notes 记录；
 *  ④ crc8 通用名非 static + `#define u8` 全局命名空间污染 → 静态化 +
 *     uint8_t；
 *  ⑤ char ack 死变量 → 收敛；校验失败页面 printf（L402）→ 剔除（返回 5）；
 *  ⑥ IIC_Start 含多余 Stop→Start 边沿（页面 L119-131——最终态正确，按
 *     页面原样保留——mspm0 版同款）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--sht30-temp-humi-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化、页外 extern 温湿度全局收敛为出参、I2C 原语静态化、延时走
 * delay 模块；页面 SHT31_Write_mode 注释掉 IIC_Stop（重复起始）按页面原样）。 */

#define SHT30_ADDR          0x44u /* ADDR 接地（页面原式 0x44<<1） */
#define SHT30_CMD_PERIODIC  0x2130u /* 周期测量：每秒 1 次高重复性 */
#define SHT30_CMD_READ      0xE000u /* 周期模式读命令（页面注释值） */
#define SHT30_READ_RETRY_MAX 20u   /* 读地址应答重试上限（页面 ≤20×2ms） */
#define SHT30_READ_RETRY_MS 2u

/* sht30_init：写周期测量模式命令（0x2130）——页面 SHT31_Write_mode(0x2130)
 * 语义（每秒 1 次高重复性测量，随后的 0xE000 读命令即时取最新数据）。 */
void sht30_init(void);

/* sht30_read：触发一次完整读取（0xE000 读命令 + 应答重试 + 6 字节回包 +
 * CRC8 两组校验 + 0.01 系数换算），返回 0 = 成功、1-5 = 页面失败码
 * （1/2/3 = 命令/地址应答失败、4 = 读地址应答超时（>20×2ms）、5 = CRC 校验
 * 失败）；成功后温度/湿度经出参带回（℃ / %RH；分辨率 0.01℃/0.01%RH，
 * 页面规格 ±0.3℃/±2%RH、SHT30 数据手册典型 ±0.2℃/±2%RH）。
 * 出参判空用 0（F1 头无 NULL）。 */
uint8_t sht30_read(float *temperature_c, float *humidity_rh);

/* sht30_read_temperature / sht30_read_humidity：便捷封装——内部完成一次
 * sht30_read，成功时结果经出参带回并返回 0，失败返回 sht30_read 的失败码
 * （出参保持原值不变）。 */
uint8_t sht30_read_temperature(float *temperature_c);
uint8_t sht30_read_humidity(float *humidity_rh);

#endif /* SHT30_STM32_H */
