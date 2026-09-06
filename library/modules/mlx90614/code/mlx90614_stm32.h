/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《MLX90614无接触测温传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/mlx90614-non-contact-temp-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef MLX90614_STM32_H
#define MLX90614_STM32_H

#include <stdint.h>

/* MLX90614 非接触红外测温传感器驱动（stm32，纯驱动切片，ADR 0009）：软 I2C
 * （SMBus 兼容，SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设、
 * 不占 TIMER），读被测目标温度（REG_OBJECT_TEMP 0x07）与环境温度
 * （REG_AMBIENT_TEMP 0x06），换算 ℃ = RAW × 0.02 − 273.15（页面公式：
 * 0.02K/LSB，内部数据 0.01℃ 分辨率，页面用 0.02 系数出整数步进）。
 * API 与 mspm0 版完全对齐（同函数名/同签名/同返回码（0=成功/1=通信失败）/
 * 出参单位 ℃——出参带回不返回温度值，0℃ 合法值不与失败混用）。
 * 引脚 = pin_config.h 单源 MLX90614_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——与批次 2 六件共挂同一软 I2C 总线（地址 0x5A 与
 * 0x38/0x23/0x40/0x44/0x50/0x1A 全异，多挂协议允许 = 合法共享）；
 * 与 motor MOTOR_A_DIR/DIR2 默认重叠：非接触测温与「带电机方向的小车运动
 * 控制」不同框、同选概率最低，同选经引脚绑定消解；页面默认 PA0/PA1 不采用
 * ——adc ADC_CH0/1 + MOTOR_A/B PWM 常备件）。
 * **SCL 输出方向初始化（批次 3 回修口径）**：init 必须
 * gpio_init(MLX90614_SCL_GPIO, MLX90614_SCL_PIN, OUT_OD) + 置高——F1 复位后
 * GPIO 为浮空输入，ODR 写入无效（批次 2 SCL 未初始化教训，防回潮守卫）；
 * 本件 init 非空实现（mspm0 版为空——syscfg 代配，stm32 版承担引脚配置，
 * notes 记录差异）。
 * 通信协议（MLX90614 SMBus / 立创移植手册）：器件地址 0x5A（默认，7 位），
 * 8 位写/读 = 0xB4/0xB5；命令字节 = bit7-5（RAM=000/EEPROM=001）+ bit4-0
 * （RAM 单位地址仅低 5 位有效，Ta=0x06、To=0x07）；读 = 写命令（地址+写，
 * ACK）→ **延时 1ms（页面注释掉的时序点——本实现加回）** → 重 start +
 * 地址+读（ACK）→ 低 8 位（ACK）+ 高 8 位（NACK）→ 停止；页面
 * PEC_Calculation（CRC-8，多项式 X8+X2+X1+1）整体注释未启用——本实现不含
 * PEC（页面演示即不校验通路，真机验证留后续，note 记录）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--mlx90614-non-contact-temp-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去掉 main.c 演示与
 * printf、函数名规范化（MLX90614_Read(SlaveAddr, RegAddr) →
 * mlx90614_read_word 静态 + read_object_temp/read_ambient_temp 服务函数）、
 * IIC 原语静态化、引脚宏参数化、延时走 delay 模块。**页面缺陷修正清单
 * （notes + 守卫）**：① **PEC/CRC 整体禁用**（定义未调用、读时序无 PEC 字节
 * ——按 mspm0 先例剔除，notes 记录）；② 失败 `return 0.0` 与合法 0℃ 混用
 * → 出参 + 状态码；③ 注释 MLX90615 笔误（不落）；④ **「必须开漏」注释 vs
 * 代码 Out_PP** → 统一 OUT_OD（总线协议 + 批次 2 先例）；⑤ 写-读间
 * `delay_ms(1)` 页面注释掉 → **加回**；⑥ 无温补/发射率修正（mspm0 同，
 * 出厂校验器件，notes）。 */

#define MLX90614_ADDR  0x5A /* 7 位器件地址（默认；8 位写/读 = 0xB4/0xB5） */
#define MLX90614_REG_AMBIENT_TEMP 0x06 /* RAM 环境温度 Ta */
#define MLX90614_REG_OBJECT_TEMP  0x07 /* RAM 被测目标温度 To */

/* mlx90614_init：SMBus 器件无上电初始化序列（出厂校验/线性化完成，页面演示
 * 也无初始化）；stm32 版 init **承担引脚配置**（SCL/SDA OUT_OD + 置高——
 * 批次 3 回修口径；mspm0 版为空实现占位（syscfg 代配），差异记录 notes）；
 * 校验是否在线由读温度判。 */
void mlx90614_init(void);

/* mlx90614_read_object_temp：读被测目标温度（寄存器 0x07），成功经出参带回
 * ℃（换算 RAW×0.02−273.15，页面公式）并返回 0；通信失败（无应答/超时）
 * 返回 1、出参不变。 */
uint8_t mlx90614_read_object_temp(float *temp_c);

/* mlx90614_read_ambient_temp：读环境温度（寄存器 0x06），语义同上。 */
uint8_t mlx90614_read_ambient_temp(float *temp_c);

#endif /* MLX90614_STM32_H */
