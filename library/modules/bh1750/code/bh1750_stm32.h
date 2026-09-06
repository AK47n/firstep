/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《BH1750光照强度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/bh1750-light-intensity-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef BH1750_STM32_H
#define BH1750_STM32_H

#include <stdint.h>

/* BH1750 光照度驱动（stm32，纯驱动切片，ADR 0009）：软 I2C 位操作读取
 * （SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设/TIMER），API
 * 与 mspm0 版完全对齐（bh1750_init/start_measure/read_lux，同函数名/同
 * 语义/同返回码）。
 * 引脚 = pin_config.h 单源 BH1750_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——与 motor MOTOR_A_DIR/DIR2 默认重叠：光照传感与「带电机
 * 方向的小车运动控制」不同框、同选概率最低；**六件软 I2C 件默认共挂此总线**
 * （地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异——环境站（温湿度+光照+EEPROM
 * 记录）合法共挂；页面默认 SDA=PB8/SCL=PB9 不采用 = 母版 OLED 段），同选时
 * 经引脚绑定消解。
 * 通信协议（BH1750FVI 数据手册 + 立创页面）：器件地址 0x23（ALT ADDRESS 接
 * 地 → 写 0x46/读 0x47；接电源宏改 BH1750_ADDR_WRITE 一处）；一次测量 =
 * Power On（0x01）→ 连续高分辨率（0x10，1 lx 分辨率、≥120ms）→ 等
 * ≥BH1750_MEASURE_DELAY_MS → 读 2 字节（高 8 位<<8|低 8 位）÷1.2 出 lx。
 * ⚠️ 页面缺陷修正清单（全部 notes 记录 + 测试守卫防回潮）：
 *  ① 读路径应答丢弃（页面 Multiple_read_BH1750 L306 读地址 I2C_WaitAck()
 *     不检查——无应答仍读）→ read_lux 检查并返回 1；
 *  ② 模板串台：页面 GY30_GPIO_Init 注释「MLX90614的引脚初始化」（红外测温
 *     页残留文案）——本实现不落；
 *  ③ 页面 BUF[8] 死全局非 static、注释块函数名「Single_Write」（缺后缀）
 *     ——收敛不落；
 *  ④ 规格表「1~65536 lx」与正文「0-65535 lx」不一致（记录不裁决）；
 *  ⑤ main 测量等待 180ms 硬编码 → BH1750_MEASURE_DELAY_MS 140 宏（≥120ms
 *     推荐值，等待归调用方——mspm0 版同款）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--bh1750-light-intensity-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化（GY30_/IIC_/Single_Write_BH1750/Multiple_read_BH1750 菜市场
 * 命名 → bh1750_init/start_measure/read_lux）、I2C 原语族静态化、引脚宏
 * 参数化、延时走 delay 模块）。 */

#define BH1750_MEASURE_DELAY_MS 140 /* 连续高分辨率测量周期 ≥120ms（手册推荐） */

/* bh1750_init：Power On（0x01——掉电模式 → 等待测量命令；无应答静默——
 * 器件上电/接线错误由 start_measure/read_lux 的返回码暴露）。 */
void bh1750_init(void);

/* bh1750_start_measure：启动连续高分辨率测量（0x10）；返回 0=成功 1=无应答
 * （器件上电/接线错误）。 */
uint8_t bh1750_start_measure(void);

/* bh1750_read_lux：读取 2 字节并换算 lx（调用前须等 ≥BH1750_MEASURE_DELAY_MS）；
 * 返回 0=成功 1=无应答；出参失败时保持原值（判空用 0——F1 头无 NULL）。 */
uint8_t bh1750_read_lux(float *lux);

#endif /* BH1750_STM32_H */
