/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《VL53L0X激光测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/vl53l0x-laser-distance-sensor.html
 * 驱动来源：立创地阔星 STM32F103C8T6 移植工程（用户网盘下载并解压）——
 *   sources/materials/lckfb-地阔星移植手册/网盘下载/vl53l0x/
 *   STM32F103C8T6_ProjectTemplate/bsp/VL53L0X/（立创 BSP 封装 +
 *   ST 官方 VL53L0X API 全套——B 类新 slug，仅 stm32 平台条目）
 * 本代码按模块库规范改写（去演示与调试输出、I2C 原语静态化、
 * 引脚宏参数化、不引 sys.h 位带等）；使用 / 复制 / 修改 / 传播
 * 请遵循立创版权要求与 ST BSD-3-Clause 许可：标明来源与链接。 */

#ifndef VL53L0X_STM32_H
#define VL53L0X_STM32_H

#include <stdint.h>

/* VL53L0X ToF 激光测距传感器驱动（stm32，纯驱动切片，ADR 0009）：
 * 软 I2C 位操作（SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C
 * 外设、不占 TIMER）+ XSHUT 复位序列；**核心 = ST 官方 VL53L0X API
 * 最小切片**（vl53l0x_core.c/h——按「纯驱动切片」规范从官方 API 全套
 * 裁剪：只保留初始化/模式配置/单次测量传递闭包，函数体原样零改动；
 * 裁剪清单 = manifest notes）。API = BSP 薄封装：
 *   vl53l0x_init()         —— XSHUT 复位序列 + 软 I2C 初始化 +
 *                             VL53L0X_DataInit（页面 vl53l0x_init 原式，
 *                             去设备 ID 校验/演示）；
 *   vl53l0x_set_mode(mode) —— 复位 + StaticInit + PerformRef* 校准 +
 *                             模式参数写入（页面 vl53l0x_set_mode 原式，
 *                             去演示；mode = 页面 BSP 枚举 0-3）；
 *   vl53l0x_read_mm(...)   —— 单次测距（页面 main 演示
 *                             VL53L0X_PerformSingleRangingMeasurement
 *                             封装——0/成功 非0/失败码，mm 出参）。
 * 量程 2 米（页面 L8/L22「温度范围:2m」串台——应为测距范围，记录），
 * 毫米输出（页面 %4imm + RangeMilliMeter），6 Pin：VCC/GND/SDA/SCL/
 * XSHUT/GPIO1（GPIO1 中断脚未用——轮询单次测量），2.6-3.5V（页面 L20）。
 * ⚠️ 器件地址 = 0x52（8bit 写 = 0x29/7bit，读 0x53）——**0x29 与
 * tcs34725 同址 → 两件互替不可同挂**（同一总线同址双选必冲突——选
 * 其一，同选经引脚绑定换独立总线或换件；bmp180×ms5611 同款口径）。
 * 引脚 = pin_config.h 单源 6 宏：VL53L0X_SCL_GPIO/_SCL_PIN 默认 PA6、
 * _SDA_GPIO/_SDA_PIN 默认 PA7（共挂批次 2/3/4 软 I2C 总线——地址 0x29
 * 与既有 14 件 0x38/0x23/0x40/0x44/0x50/0x1A/0x48/0x5A/0x58/0x40/0xEE 等
 * 全异 = 合法共挂；与 motor MOTOR_A_DIR/DIR2 默认重叠：ToF 测距与「带
 * 电机方向的小车运动控制」不同框、同选概率最低，同选经引脚绑定消解）、
 * _XSHUT_GPIO/_XSHUT_PIN 默认 PB0（叠 hx711 DT + EC11 SW——ToF 与称重/
 * 旋钮不同框；**页面/移植工程默认 PB7 弃用** = human_ir/GRAY_D8 组常备）。
 *
 * 电平口径（与共总线件统一）：页面/移植工程 i2c.c 原式
 * GPIO_Mode_Out_PP（推挽）+ GPIO_Mode_IPU → 模块 OUT_OD/IU——PA6/PA7
 * 与批次 2/3/4 软 I2C 件共挂总线，推挽×开漏同总线互斥（同轨道两输出
 * 驱动电平可能打架）；模块板自带上拉电阻（bmp180 同款注释口径）；
 * SCL/SDA 初始化显式置高（批次 3/01 回修口径：F1 复位后 GPIO 浮空
 * 输入、ODR 写入无效——总线空闲电平必须显式置高）。
 * 位时序 = 页面软 I2C 原式（SCL 半周期 5us ≈ 100kHz 级总线速度；
 * 页面 BSP 声明的 comms_speed_khz=400 仅是 ST 元数据——不驱动时序）。
 *
 * ⚠️ 缺陷修正清单（全部 notes 记录 + 测试守卫防回潮）：
 *  ① 页面 main 演示 Status 错误粘滞（L103-111——首错后永不再测）
 *     → read_mm 每次调用独立状态、无粘滞（永远重试；
 * ② 页面 vl53l0x_data 无声明（L106——块内无 extern/声明）
 *     → 模块内 static 实例（vl53l0x_data 收敛模块静态）；
 *  ③ 立创 BSP vl53l0x_init 把器件地址改到 0x54（8bit）且
 *     `vl53l0x_Addr_set(...,0x54)` 返回值未判（if(Status) 读的是
 *     初始化前 Status）→ 本件**保持上电默认 0x52/0x29**（地址重设族
 *     整族裁剪——最小切片 + 0x29 同址警示以默认址为准；记录差异）；
 *  ④ 立创 BSP vl53l0x_gen.h/断言等演示（vl53l0x_test/print_pal_error/
 *     mode_string/vl53l0x_info/One_measurement 仅声明未定义）→ 全部
 *     范围外（One_measurement 在网盘包内只有声明没有实现——记录）；
 *  ⑤ 移植工程 i2c.c I2C_WaitAck `char ack` 死变量（只读未写恒 0）
 *     → 剔除（bmp180 批 4 修正口径）；
 *  ⑥ 移植工程 fix: VL53L0X_write_word 奇地址分支两次写 index
 *     （低字节未写）→ 按 ST 原式第二字节 index+1（写 word 寄存器
 *     奇地址路径——模块内 `vl53l0x_iic_write_word`）；
 *  ⑦ 校准 = 每次 set_mode 执行 PerformRefSpadManagement +
 *     PerformRefCalibration（页面 BSP 原语义——性能代价 ~ms 级、
 *     无传感器校准缓冲）；立创 BSP 的校准缓存路径（AjustOK/24c02
 *     写读——依赖 AT24C02 演示件、AjustOK 恒 0 不可达）剔除；
 *  ⑧ 电平口径 Out_PP → OUT_OD 见上 + 页面 GPIO_Init/RCC 调用全部
 *     → ml_gpio（gpio_init 内部做时钟使能）；XSHUT GPIO_Mode_Out_PP
 *     → OUT_PP（页面原式——单脚推挽无共总线冲突）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/
 * sensor--vl53l0x-laser-distance-sensor.md（立创 wiki 地阔星移植手册；
 * 页内仅 1 个 main 演示块——驱动全页外，本件全部取自移植工程）。 */

/* 模式（页面 BSP 枚举原式） */
#define VL53L0X_MODE_DEFAULT 0u        /* 默认：33ms 预算，14/10 VCSEL */
#define VL53L0X_MODE_HIGH_ACCURACY 1u  /* 高精度：200ms 预算 */
#define VL53L0X_MODE_LONG_RANGE 2u     /* 长距离：18/14 VCSEL */
#define VL53L0X_MODE_HIGH_SPEED 3u     /* 高速：20ms 预算 */

/* vl53l0x_init：XSHUT 复位序列 + 软 I2C 初始化 + DataInit（页面
 * vl53l0x_init 原式——XSHUT 关 50ms/开 50ms 后 DataInit；去设备 ID
 * 校验 vl53l0x_info/演示）。返回 0 = 成功、非 0 = ST API 状态码。 */
uint8_t vl53l0x_init(void);

/* vl53l0x_set_mode：按模式（0-3）配置测量参数（页面 vl53l0x_set_mode
 * 原式——复位 + StaticInit + PerformRefSpadManagement +
 * PerformRefCalibration + SetDeviceMode(SINGLE_RANGING) + 限检/预算/
 * VCSEL 写入；mode 索引页面 Mode_data 参数表：默认/高精度/长距离/高速
 * 的 signalLimit/sigmaLimit/timingBudget/preRangeVcselPeriod/
 * finalRangeVcselPeriod）。返回 0 = 成功、非 0 = ST API 状态码。 */
uint8_t vl53l0x_set_mode(uint8_t mode);

/* vl53l0x_read_mm：单次测距（页面 main 演示
 * VL53L0X_PerformSingleRangingMeasurement + RangeMilliMeter 封装）——
 * 每次调用独立状态（缺陷①修正：无 Status 粘滞——永远重试测距）。
 * 返回 0 = 成功、非 0 = ST API 状态码；*dist_mm = 距离毫米（float——
 * 页面 mm 输出，出参可传 0 只判状态；RangeStatus 细分页外——调用方
 * 如需按 RangeStatus 判无效读数值可扩展，本件按 BSP 原式不检查）。 */
uint8_t vl53l0x_read_mm(float *dist_mm);

#endif /* VL53L0X_STM32_H */
