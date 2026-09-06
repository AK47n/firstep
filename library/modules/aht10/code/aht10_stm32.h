/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AHT10温湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/aht10-temp-humi-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef AHT10_STM32_H
#define AHT10_STM32_H

#include <stdint.h>

/* AHT10 温湿度传感器驱动（stm32，纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设、不占 TIMER），
 * 读取温湿度并按换算公式出摄氏度 / 百分比相对湿度。API 与 mspm0 版完全
 * 对齐（aht10_init/read/read_temperature/read_humidity，同函数名/同语义/
 * 同返回码）。
 * 引脚 = pin_config.h 单源 AHT10_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——与 motor MOTOR_A_DIR/DIR2 默认重叠：环境传感与「带电机
 * 方向的小车运动控制」不同框、同选概率最低；**六件软 I2C 件默认共挂此总线**
 * （地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异，多挂协议允许——合法共享），
 * 与既有 I2C_GPIO（PA11/12 USB 共用脚）/OLED_GPIO（PB8/9）零重叠），同选时
 * 经引脚绑定消解（逐脚端口宏，换脚零组约束）。
 * 通信协议（AHT10 数据手册 + 立创页面）：器件地址 0x38（页面前置 0x70 =
 * 0x38<<1 写 / 0x71 读）；先发校准命令（0xE1 0x08 0x00），再发触发测量
 * （0xAC 0x33 0x00），间隔 ≥20ms 后读 6 字节（状态 + 湿度 20 位 + 温度
 * 20 位）。换算（页面原式）：湿度 = data/2^20×100；温度 = data/2^20×200-50。
 * ⚠️ 页面缺陷修正清单（全部 notes 记录 + 测试守卫防回潮）：
 *  ① 每读后重复复位+初始化（页面 AHT10_Read 尾调 AHT10Reset()+
 *     AHT10_GPIO_Init()——多 ~100ms 且读后即复位）→ 合并进 init；
 *  ② 页面 GPIO_Init 内 Send_Byte 0x70/0xE1/0x08/0x00 连发无应答检查 → 补
 *     wait_ack（照页面 Read 段正确做法）；
 *  ③ 页面读地址重试 do-while 后不判超时（超时仍读垃圾）→ timeout>=5 返回 1；
 *  ④ 页面 L339 注释「器件地址+写命令」与值 0x71（读地址）矛盾；
 *  ⑤ 页面 char timeout/冗余 ack 变量（类型宽度）→ uint8_t 收敛。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--aht10-temp-humi-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化（AHT10_Read→aht10_read、Get_Temperature/Get_Humidity→
 * read_temperature/read_humidity）、全局温湿度缓存改出参、I2C 原语族
 * 静态化、引脚宏参数化、延时走 delay 模块）。 */

/* aht10_init：上电稳定 + 校准（50ms 稳定 + 0xE1 0x08 0x00——页面校准序列，
 * 补应答检查；页面「每次读后重复复位初始化」已消（缺陷①）。 */
void aht10_init(void);

/* aht10_read：触发一次测量并读取，返回 0 = 成功、1 = 超时/无应答（页面
 * 返回 0 恒成功——缺陷③修正：超时后不再读垃圾数据）；成功后温度/湿度经
 * 出参带回（单位 ℃ / %RH，出参可传 NULL）。 */
uint8_t aht10_read(float *temperature_c, float *humidity_rh);

/* aht10_read_temperature：读取温度（℃）；内部自动完成一次测量。 */
float aht10_read_temperature(void);

/* aht10_read_humidity：读取相对湿度（%RH）；内部自动完成一次测量。 */
float aht10_read_humidity(void);

#endif /* AHT10_STM32_H */
