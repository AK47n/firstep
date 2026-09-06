/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《MS5611气压传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ms5611-pressure-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef MS5611_STM32_H
#define MS5611_STM32_H

#include <stdint.h>

/* MS5611-01BA03 高精度气压/温度传感器驱动（stm32，纯驱动切片，ADR 0009）：
 * 软 I2C 位操作（SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设、
 * 不占 TIMER），ms5611_init 封装页面 main 序列（复位 0x1E → delay 300ms →
 * Read_PROM 8 字 C1..C6+CRC——校准数据 init 缓存为模块静态）+ ms5611_read
 * 出温度（℃，0.01℃ 分辨率——页面整数℃截断修正）与气压（Pa，P 单位
 * 0.01mbar == 1Pa——页面 /100 = hPa 统一为 Pa 修正）+ ms5611_read_altitude
 * 出海拔（米，44330 公式——与 bmp180 共用换算，math.h/pow）。
 * API 与 mspm0 版完全对齐（ms5611_init/read/read_altitude，同函数名/同语义/
 * 同返回码/同出参单位）。
 * ⚠️ **64 位换算（本件核心——页面 uint32_t 缺陷人工复核修正）**：页面
 * dT 声明为 uint32_t——低于 20℃ 时 dT = D2−C5×256 为负、无符号回绕破坏
 * TEMP/OFF/SENS/P；且 `C4×dT/128`、`C3×dT/256.0` 以 uint16_t×uint32_t 在
 * **32 位 unsigned int 乘法**评估 → 溢出（积可达 5.5e11 ≫ 2^32，全温区多数
 * 读数偏差数十 hPa）。本件 dT 全程**有符号 64 位 long long**（表达式不变，
 * 标准实现 int64 口径——mspm0 批 13 修正同款沿用），测试以 int64 镜像基线
 * 钉死（test_module_ms5611.py）。
 * 引脚 = pin_config.h 单源 MS5611_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——**共挂批次 2/3 软 I2C 总线**：地址 0xEE 与既有 11 件全异
 * = 合法共挂；**与 bmp180 同址 0xEE → 两件互替不可同挂**（同一总线同址双选
 * 必冲突——选一只，同选经引脚绑定换独立总线或换件），notes 记录；与 motor
 * MOTOR_A_DIR/DIR2（电机方向）默认重叠：气压/海拔与「带电机方向的小车运动
 * 控制」不同框、同选概率最低，同选经引脚绑定消解；页面默认 SDA=PB9/
 * SCL=PB8 不采用 = 母版 OLED 段）。
 * 通信协议（页面资料 + MS5611 数据手册）：器件地址 0xEE（写）/0xEF（读）
 * （CSB 高 = 1110 110；PS 上拉 = I2C 模式）；复位命令 0x1E；PROM 基址
 * 0xA0 + i*2（i=0..7：厂家信息 + C1..C6 + CRC）；转换命令 0x48 = D1 气压
 * （OSR 4096）/ 0x58 = D2 温度（OSR 4096，12 比特半位翻转后 0x00 读取）；
 * 换算（页面原式）：dT=D2−C5×256、TEMP=2000+dT×C6/2^23（0.01℃）、
 * OFF=C2×2^16+C4×dT/128、SENS=C1×2^15+C3×dT/256、P=(D1×SENS/2^21−OFF)/2^15
 * （0.01mbar == Pa）。
 * ⚠️ 页面缺陷修正清单（全部 notes 记录 + 测试守卫防回潮）：
 *  ① dT 改有符号 64 位 long long（负温回绕 + 32 位乘法溢出——核心）；
 *  ② 温度出参 TEMP/100.0（0.01℃ 分辨率——页面整数℃截断修正）；
 *  ③ 气压出参 P（Pa——页面 /100 = hPa 修正，P 单位 0.01mbar==1Pa）；
 *  ④ PROM 读补逐段应答检查（页面 I2C_WaitAck 无判断——返回 3）；
 *  ⑤ 段间 2×10ms 等待保留（页面 Get_TEMP 两次转换间各 delay_ms(10)）；
 *  ⑥ 页面 Get_pressure 内嵌重复调 Get_TEMP 二次重读合并（单次 D1/D2）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--ms5611-pressure-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化、IIC 原语静态化、main 序列封装 init、全局收敛模块静态）。 */

#define MS5611_ADDR_W 0xEEu /* 器件地址+写（页面 0xee|0；CSB 高） */
#define MS5611_ADDR_R 0xEFu /* 器件地址+读（页面 0xee|1；CSB 高） */
#define MS5611_CMD_RESET 0x1Eu  /* 复位命令（页面 0x1e） */
#define MS5611_CMD_D1 0x48u     /* 气压转换命令 OSR=4096（页面 0x48） */
#define MS5611_CMD_D2 0x58u     /* 温度转换命令 OSR=4096（页面 0x58） */
#define MS5611_PROM_BASE 0xA0u  /* PROM 基址（页面 0xA0 + i*2，8 字） */
#define MS5611_PROM_WORDS 8u
#define MS5611_CONV_WAIT_MS 10u /* 转换等待（页面 10ms——命令/读取两段各一次） */
#define MS5611_INIT_WAIT_MS 300u /* 复位后等待初始化完成（页面 300ms） */

/* ms5611_init：页面 main 序列封装——引脚配置（SCL OUT_OD 初始化+置高——
 * 批次 3/01 回修口径）→ 复位 0x1E（返回 0 = 成功、1 = 器件地址错误、
 * 2 = 命令无应答——页面码）→ delay 300ms → Read_PROM 8 字（0xA0..0xAE：
 * C1..C6 = idx1..6 + CRC = idx7，页面原式；**页面 PROM 读的 I2C_WaitAck
 * 无应答检查缺漏——人工复核修正：逐段检查应答并返回 3 = PROM 读应答失败**，
 * notes 记录）。 */
uint8_t ms5611_init(void);

/* ms5611_read：触发一次 D1/D2 转换并换算（页面 Get_TEMP 的 2 次转换按原式
 * + Get_pressure 换算合并——单次 D1/D2 读取 + 一次 dT/TEMP/OFF/SENS/P
 * 全换算，页面 Get_pressure 内嵌重复调 Get_TEMP 的二次重读省去，结果等价，
 * notes 记录；**dT/OFF/SENS/P 全程有符号 64 位 long long**）。返回
 * 0 = 成功、1 = D1 段失败、2 = D2 段失败、3 = 数据读失败（读地址无应答——
 * 页面 NACK printf 改码，段内细分码 1-5 保留内部）；成功后温度/气压经出参
 * 带回（℃ 0.01 分辨率——页面 Get_TEMP 整数℃截断 dat=(TEMP/1000)*10+
 * (TEMP/100%10) 丢小数，人工复核修正；Pa——P 单位 0.01mbar == 1Pa，页面
 * /100 = hPa，统一出 Pa；出参可传 0——F1 头无 NULL）。 */
uint8_t ms5611_read(float *temp_c, float *pressure_pa);

/* ms5611_read_altitude：气压→海拔换算（与 bmp180 共用 44330 公式——
 * math.h/pow，ir_distance 编译先例；两件分工见 manifest notes），p 单位 Pa，
 * 返回海拔米。 */
float ms5611_read_altitude(float pa);

#endif /* MS5611_STM32_H */
