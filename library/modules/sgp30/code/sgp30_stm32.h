/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《SGP30气体传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/sgp30-gas-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef SGP30_STM32_H
#define SGP30_STM32_H

#include <stdint.h>

/* SGP30 空气质量传感器驱动（stm32 纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设、不占 TIMER），
 * 读取 TVOC（总挥发性有机物，ppb）与 CO2 当量（ppm）。API 与 mspm0 版完全
 * 对齐（同函数名/同签名/同返回码 0-5/出参单位 ppb+ppm）。
 * 引脚 = pin_config.h 单源 SGP30_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——与批次 2 六件共挂同一软 I2C 总线（地址 0x58 与
 * 0x38/0x23/0x40/0x44/0x50/0x1A 全异，多挂协议允许 = 合法共享）；
 * 与 motor MOTOR_A_DIR/DIR2 默认重叠：空气质量传感与「带电机方向的小车
 * 运动控制」不同框、同选概率最低，同选经引脚绑定消解；页面默认 PB8/PB9
 * 不采用 = 母版 OLED_GPIO 段）。
 * **SCL 输出方向初始化（批次 3 回修口径）**：init 必须
 * gpio_init(SGP30_SCL_GPIO, SGP30_SCL_PIN, OUT_OD) + 置高——F1 复位后 GPIO
 * 为浮空输入，ODR 写入无效（批次 2 SCL 未初始化教训，防回潮守卫）。
 * 通信协议（SGP30 数据手册 + 立创页面）：器件地址 0x58（写 0xB0/读 0xB1）；
 * 初始化命令 0x2003（init_air_quality，空气特征值/基准）；测量命令 0x2008
 * （measure_air_quality）——页面写命令内嵌 delay_ms(100) 覆盖器件测量时长；
 * 回包 6 字节 = CO2 高/低 + CRC + TVOC 高/低 + CRC，CRC8（多项式 0x31、初值
 * 0xFF——同 SHT30/AGS10 系）两组校验（**页面实现缺 CRC 校验且只读 5 字节漏
 * TVOC CRC 字节，按数据手册修正——器件正确性修正**，缺陷①）。
 * 上电需 15s 左右预热：预热期 CO2=400ppm、TVOC=0ppb 恒定，读到 TVOC≠0 且
 * CO2≠400 才算初始化完成（**判定归生成骨架/调用方循环**，页面正文有述、
 * 代码未实现——不内嵌死等 15s）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--sgp30-gas-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化、IIC 原语静态化、延时走 delay 模块、打包值 uint32_t 收敛为
 * 双出参 + 状态码。**页面缺陷修正清单（notes + 守卫）**：① **CRC 缺失
 * （主缺陷）**：`crc=crc` 自赋值丢弃 + 只读 5 字节漏 TVOC CRC → 读满 6 字节 +
 * 两组 CRC8（0x31/0xFF）校验（失败=5）；② 读写路径 NACK 全丢 → 补检查与
 * 失败码（1-4）；③ 正文「为 0 是读、为 1 是写」语义写反（示例/代码正确——
 * 记录不裁决）；④ 15s 预热判定仅正文未实现 → 归调用方；⑤ 页面默认脚与
 * ADS1115 页互换记录（不裁决）。 */

#define SGP30_ADDR              0x58u /* 7bit 地址（页面 0x58<<1=0xB0 写/读 0xB1） */
#define SGP30_CMD_INIT_AIR      0x2003u /* init_air_quality：初始化空气特征基准 */
#define SGP30_CMD_MEASURE_AIR   0x2008u /* measure_air_quality：读取空气质量值 */

/* sgp30_init：引脚配置（SCL/SDA OUT_OD + 置高——批次 3 回修口径）+ 发送
 * 0x2003 初始化空气特征值/基准（页面 SGP30_Init 语义）；上电预热 15s 左右，
 * 预热判定（TVOC≠0 且 CO2≠400）归调用方循环。 */
void sgp30_init(void);

/* sgp30_read：发 0x2008 测量命令（写命令内嵌延时覆盖器件测量时长）+ 读
 * 6 字节回包 + CRC8 两组校验，TVOC/CO2 经出参带回（ppb / ppm；出参判空
 * 用 0——F1 头无 NULL）。
 * 返回 0 = 成功；1/2/3 = 写命令地址/命令字节应答失败（页面原式无应答检查，
 * 按 sht30 风格补）；4 = 读地址应答失败；5 = CRC 校验失败（器件正确性修正
 * ——页面缺校验）。 */
uint8_t sgp30_read(uint16_t *tvoc_ppb, uint16_t *co2_ppm);

#endif /* SGP30_STM32_H */
