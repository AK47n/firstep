/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《BMP180气压传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/bmp180-pressure-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef BMP180_STM32_H
#define BMP180_STM32_H

#include <stdint.h>

/* BMP180 气压/温度/海拔传感器驱动（stm32，纯驱动切片，ADR 0009）：软 I2C
 * 位操作（SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设、不占
 * TIMER），bmp180_init 读 11 项出厂校准系数（页面 BMP180_Get_param 序列入
 * init——校准数据是每次读数的必需输入，init 缓存为模块静态，sgp30_init 先例）
 * + bmp180_read 出温度（℃）/气压（Pa）（页面 Get_Temperature + Get_Pressure
 * **原式合并**——气压段复用 B5，页面 Get_Pressure 内嵌重复调 Get_Temperature
 * 的二次读取省去，结果等价）+ bmp180_read_altitude 出海拔（米，页面 44330
 * 公式，math.h/pow——ARMCC 标准库自动含 math，uvprojx 无需显式链接项，
 * ir_distance/pid 先例）。API 与 mspm0 版完全对齐（bmp180_init/read/
 * read_altitude，同函数名/同语义/同返回码/同出参单位 ℃ 与 Pa）。
 * 引脚 = pin_config.h 单源 BMP180_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——**共挂批次 2/3 软 I2C 总线**：地址 0xEE 与既有 11 件
 * 0x38/0x23/0x40/0x44/0x50/0x1A/0x48/0x29/0x5A/0x58/0x40 全异 = 合法共挂；
 * **与 ms5611 同址 0xEE → 两件互替不可同挂**（同一总线同址双选必冲突——
 * 选其一，同选经引脚绑定换独立总线或换件），notes 记录；与 motor
 * MOTOR_A_DIR/DIR2（电机方向）默认重叠：气压/海拔与「带电机方向的小车运动
 * 控制」不同框、同选概率最低，同选经引脚绑定消解；页面默认 SDA=PB9/
 * SCL=PB8 不采用 = 母版 OLED 段）。
 * 通信协议（页面资料 + BMP180 数据手册）：器件地址 0xEE（写）/0xEF（读）；
 * 命令寄存器 0xF4——温度 0x2E、气压 0x34+(oss<<6)（本件固定 oss=0 =
 * ultra low power 页面默认，参数化范围外）；校准系数地址 0xAA..0xBE
 * （AC1..MD 共 11 项，高八位在 MSB 地址）；温度换算 T=((B5+8)/16.0)*0.1
 * （每数值 0.1℃）、气压换算页面全套原式（单位 Pa）。
 * ⚠️ 页面缺陷修正清单（全部 notes 记录 + 测试守卫防回潮）：
 *  ① Get_Pressure 内嵌 Get_Temperature 二次转换重读合并（B5 复用）；
 *  ② NACK 仅 printf → 状态码（0=成功/1=温度段失败/2=气压段失败）；
 *  ③ char ack 死变量剔除；
 *  ④ B7 uint32_t 双分支保留（B7 = ((uint32)UP−(uint32)B3)×50000 可达
 *     ≥2^31——else 分支不可删，按页面/标准保留真/假双分支 + 注释）；
 *  ⑤ 掩码 & 0xFFFC 不得出现（BMP180 无此掩码——反向守卫）；
 *  ⑥ 页面默认脚 PB8/PB9 不照抄（=母版 OLED 段）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--bmp180-pressure-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化、IIC 原语静态化、校准读取封装 init、全局 param/B5 收敛模块
 * 静态、NACK printf 改状态码返回）。 */

#define BMP180_ADDR_W 0xEEu /* 器件地址+写（页面 0XEE） */
#define BMP180_ADDR_R 0xEFu /* 器件地址+读（页面 0XEF） */
#define BMP180_REG_CTRL_MEAS 0xF4u /* 命令寄存器（页面 0xf4） */
#define BMP180_CMD_TEMP 0x2Eu      /* 温度读取命令（页面 0x2E） */
#define BMP180_CMD_PRES 0x34u      /* 气压读取命令 oss=0（页面 0x34） */
#define BMP180_OSS 0u /* 工作模式：固定 0 = ultra low power（页面默认，参数化范围外） */

/* bmp180_init：读 11 项出厂校准系数（页面 BMP180_Get_param 序列原式：
 * 0xAA..0xBE 逐项 Read16 入模块静态——AC1..MD；校准数据是每次读数的
 * 必需输入，init 缓存为静态。返回 0 = 成功、1 = 校准读取段失败。
 * ⚠️ 内含 SCL OUT_OD 初始化 + 置高（批次 3/01 回修口径：F1 复位后 GPIO
 * 浮空输入、ODR 写入无效——总线空闲电平必须显式置高）。 */
uint8_t bmp180_init(void);

/* bmp180_read：触发一次完整读取（页面 Get_Temperature + Get_Pressure
 * 原式合并——温度段 0xF4←0x2E→delay 6ms→读 0xF6 2 字节→X1/X2/B5/T，
 * 气压段 0xF4←0x34+(oss<<6)→delay 10ms→读 0xF6 3 字节→B6..B7/p 全套；
 * B5 复用 = 省去页面 Get_Pressure 内嵌重复调 Get_Temperature 的二次读取）。
 * 返回 0 = 成功、1 = 温度段失败、2 = 气压段失败（段内细分码写地址/命令/
 * 读地址超时 5×1ms 保留在底层，段级映射 sht20 先例）；成功后温度/气压经
 * 出参带回（℃ / Pa，页面「T 每数值 0.1℃、p 每数值 1Pa」；出参可传 0——
 * 只取一路，F1 头无 NULL）。 */
uint8_t bmp180_read(float *temp_c, float *pa);

/* bmp180_read_altitude：气压→海拔换算（页面原式 44330×(1-pow(p/101325,
 * 1/5.255))，math.h/pow——ir_distance 编译先例），p 单位 Pa，返回海拔米。 */
float bmp180_read_altitude(float pa);

#endif /* BMP180_STM32_H */
