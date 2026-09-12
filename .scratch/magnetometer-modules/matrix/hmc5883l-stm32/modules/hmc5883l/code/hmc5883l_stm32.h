/* 来源：Honeywell HMC5883L 三轴数字磁力计数据手册（Datasheet 900405 Rev E）。
 * 库内与桌面工作目录遗留的旧实现 ml_hmc5883l（多份副本逐字节相同）的缺陷
 * 清单见下——本文件是重写。 */

#ifndef HMC5883L_STM32_H
#define HMC5883L_STM32_H

#include <stdint.h>

/* HMC5883L 三轴磁力计 / 电子罗盘驱动（stm32，纯驱动切片，ADR 0009）：
 * 软 I2C 位操作（SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设/
 * TIMER），API 与 mspm0 版完全对齐（同名 / 同语义 / 同返回码）。
 * 引脚 = pin_config.h 单源 HMC5883L_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——库内软 I2C 总线共享组：与 aht10/bh1750/sht20/sht30/
 * at24c02/ags10/ads1115/vl53l0x/mlx90614 共挂，器件地址全异合法；本件
 * 0x3C/0x3D 与其余件零冲突）。
 * 器件：7 位地址 0x1E → 写 0x3C / 读 0x3D；数据区顺序 X-Z-Y（非 X-Y-Z）；
 * ID 寄存器 0x0A..0x0C = 'H','4','3'。
 *
 * ⚠️ 旧实现缺陷清单（六条，全部修正 + notes 记录 + 测试守卫防回潮）：
 *  ① 读地址当寄存器用：旧 `HMC5883L_Read(addr)` 写 addr 后再发
 *     `HMC5883L_ADDR | 0x01`（= 0x3D，把读地址当寄存器地址发出）——
 *     本实现读写地址两宏分列（HMC5883L_ADDR_WRITE/READ），读用 0x3D；
 *  ② 寄存器命名误导：旧宏 DOXMR 0x03 / DOZMR 0x05 / DOYMR 0x07 按 X-Y-Z
 *     命名，实际器件顺序为 X-Z-Y——本实现宏名与手册一致并注释标注；
 *  ③ 无符号扩展：旧 `hmc_x = data_l | (data_h << 8)` 把负磁场读成
 *     32768+ 的大正数——本实现 (int16_t)(((uint16_t)hi << 8) | lo)；
 *  ④ 死全局：旧 `float yaw_hmc;` 声明后从未赋值（航向角名义存在、实际
 *     不可用）——本实现 hmc5883l_read_heading 真出 0–360°；
 *  ⑤ CRA 取值存疑：旧写 0xF8（数据手册表 4 合法组合为 0x70/0x78/0x68 等，
 *     0xF8 落在保留区间）——本实现按手册取 0x70（8 次平均 / 15Hz / 正常）；
 *  ⑥ 从不验 ID、ACK 全忽略：旧 init 直接写三个寄存器，器件拔了/接错/换成
 *     QMC5883L 也「初始化成功」——本实现 init 先读 ID 三字节，失败返回 1
 *     （总线无应答）/ 2（型号不符）。
 *
 * 航向换算不引 math.h：四象限 arctan 有理逼近内联实现（免链 libm，
 * 且纯函数可数值单测）。 */

#define HMC5883L_ADDR_WRITE 0x3C /* 7 位 0x1E << 1 */
#define HMC5883L_ADDR_READ 0x3D

#define HMC5883L_REG_CRA 0x00
#define HMC5883L_REG_CRB 0x01
#define HMC5883L_REG_MR 0x02
#define HMC5883L_REG_DATA_X_MSB 0x03
#define HMC5883L_REG_DATA_X_LSB 0x04
#define HMC5883L_REG_DATA_Z_MSB 0x05
#define HMC5883L_REG_DATA_Z_LSB 0x06
#define HMC5883L_REG_DATA_Y_MSB 0x07
#define HMC5883L_REG_DATA_Y_LSB 0x08
#define HMC5883L_REG_STATUS 0x09
#define HMC5883L_REG_ID_A 0x0A
#define HMC5883L_REG_ID_B 0x0B
#define HMC5883L_REG_ID_C 0x0C

#define HMC5883L_ID_A_VALUE 0x48 /* 'H' */
#define HMC5883L_ID_B_VALUE 0x34 /* '4' */
#define HMC5883L_ID_C_VALUE 0x33 /* '3' */

#define HMC5883L_DATA_LEN 6

#define HMC5883L_CRA_8AVG_15HZ_NORMAL 0x70
#define HMC5883L_CRB_GAIN_1_3GA 0x20
#define HMC5883L_MR_CONTINUOUS 0x00

#define HMC5883L_RAD_TO_DEG 57.29577951308232f

/* hmc5883l_init：两脚初始化（SCL OUT_OD + 置高）→ 验 ID → 配置 CRA/CRB/MR；
 * 返回 0=成功、1=总线无应答、2=器件 ID 不符。 */
uint8_t hmc5883l_init(void);

/* hmc5883l_read：三轴原始值（16 位有符号，已符号扩展）；出参可传 0 表示
 * 不取该轴（F1 头无 NULL）；返回 0=成功 1=读失败。 */
uint8_t hmc5883l_read(int16_t *x, int16_t *y, int16_t *z);

/* hmc5883l_heading_from_xy：航向角纯函数（0–360°，顺时针；X 轴 0°）。
 * 零向量返回 0（不产生 NaN）。独立暴露供单测直接调用。 */
float hmc5883l_heading_from_xy(float x, float y);

/* hmc5883l_read_heading：读三轴后出航向角；x_off/y_off = 硬铁偏移（不校正
 * 传 0）；返回 0=成功 1=读失败。 */
uint8_t hmc5883l_read_heading(float *deg, int16_t x_off, int16_t y_off);

#endif /* HMC5883L_STM32_H */
