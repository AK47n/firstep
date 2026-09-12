/* 来源：Honeywell HMC5883L 三轴数字磁力计数据手册（Datasheet 900405 Rev E）。
 * 库内（含桌面工作目录）留有旧实现 ml_hmc5883l（三处逐字节相同）：本模块是
 * **重写**，不是搬运——旧实现的确定性缺陷见下方「旧实现缺陷清单」。
 * 使用 / 复制 / 修改请遵循器件厂商与数据手册的版权要求。 */

#ifndef HMC5883L_H
#define HMC5883L_H

#include <stdint.h>

/* HMC5883L 三轴磁力计 / 电子罗盘驱动（mspm0 纯驱动，ADR 0009）：
 * - 软 I2C 位操作（不占硬件 I2C 外设、不占 TIMER，SDA 方向运行时切换，照
 *   aht10/bh1750 先例）；SCL/SDA = 母版 syscfg 实例 HMC5883L 两脚（默认
 *   PB6/PB7）；
 * - 器件 7 位地址 0x1E → 写 0x3C / 读 0x3D（两宏分列，读地址不得当寄存器用）；
 * - 初始化三件事：**先验 ID**（0x0A..0x0C = 'H','4','3'）→ 配置 CRA/CRB/MR
 *   → 连续测量模式；此后直接读数据区即可；
 * - API 与 stm32 版完全对齐（同名 / 同语义 / 同返回码）。 */

/* 器件地址：7 位 0x1E 左移一位后的完整地址字节（写 0x3C / 读 0x3D）。
 * 旧实现只定义 ADDR 一个宏、读时写 ADDR | 0x01（= 0x3D 当寄存器发），
 * 本实现把读写两态显式分列——缺陷清单①。 */
#define HMC5883L_ADDR_WRITE 0x3C
#define HMC5883L_ADDR_READ 0x3D

/* 寄存器（数据手册 900405 Rev E 表 3；器件数据区顺序 = X-Z-Y 而非 X-Y-Z） */
#define HMC5883L_REG_CRA 0x00
#define HMC5883L_REG_CRB 0x01
#define HMC5883L_REG_MR 0x02
#define HMC5883L_REG_DATA_X_MSB 0x03 /* X 高 8 位（DOXMR） */
#define HMC5883L_REG_DATA_X_LSB 0x04 /* X 低 8 位（DOXLR） */
#define HMC5883L_REG_DATA_Z_MSB 0x05 /* Z 高 8 位（DOZMR） */
#define HMC5883L_REG_DATA_Z_LSB 0x06 /* Z 低 8 位（DOZLR） */
#define HMC5883L_REG_DATA_Y_MSB 0x07 /* Y 高 8 位（DOYMR） */
#define HMC5883L_REG_DATA_Y_LSB 0x08 /* Y 低 8 位（DOYLR） */
#define HMC5883L_REG_STATUS 0x09
#define HMC5883L_REG_ID_A 0x0A /* 器件 ID 三字节：'H' '4' '3' */
#define HMC5883L_REG_ID_B 0x0B
#define HMC5883L_REG_ID_C 0x0C

#define HMC5883L_ID_A_VALUE 0x48 /* 'H' */
#define HMC5883L_ID_B_VALUE 0x34 /* '4' */
#define HMC5883L_ID_C_VALUE 0x33 /* '3' */

#define HMC5883L_DATA_LEN 6 /* 数据区 6 字节（X/Z/Y 各 2 字节，大端） */

/* CRA（0x00）：MA1:MA0 = 00 正常测量、DO2:DO0 = 111 8 次平均、MS1:MS0 = 00
 * 15Hz → 0x70。
 * ⚠️ 缺陷清单⑤：旧实现写的 CRA 值落在保留/未定义组合区间（其高四位取值
 * 与数据手册表 4 的合法组合 0x70 / 0x78 / 0x68 等均不符），来源不明——
 * 本实现按手册取值 0x70。 */
#define HMC5883L_CRA_8AVG_15HZ_NORMAL 0x70

/* CRB（0x01）：GN2:GN0 = 001 → 增益 ±1.3Ga（1090 LSB/Gauss，出厂默认） */
#define HMC5883L_CRB_GAIN_1_3GA 0x20

/* MR（0x02）：MD1:MD0 = 00 → 连续测量模式（初始化后直接读数据区即可） */
#define HMC5883L_MR_CONTINUOUS 0x00

/* 航向换算辅助（库内私有实现，见 .c）：四象限 arctan 有理逼近
 * atan(z) ≈ z(0.9998660 − 0.3302995z² + 0.1801410z⁴ − 0.0851330z⁶ + 0.0208351z⁸)
 * （z = |y/x| ∈ [0,1]）——**不引 math.h**：省掉裸机浮点库链接依赖
 * （CCS/Keil 双工具链都不必额外链 libm），且纯函数在无硬件时也能数值验证。
 * 精度约 ±0.01°（库内不依赖更高精度，校准/拟合属生成骨架范围）。 */
#define HMC5883L_RAD_TO_DEG 57.29577951308232f

/* hmc5883l_init：验 ID + 配置三寄存器；返回 0=成功、1=总线无应答（器件未
 * 上电 / 接线错误）、2=器件 ID 不符（接错型号——市售「HMC5883L 模块」多为
 * QMC5883L，两者寄存器语义完全不同）。
 * ⚠️ 缺陷清单⑥：旧实现从不验 ID、所有 I2C 原语忽略 ACK —— 拔了器件也
 * 「初始化成功」，随后静默读出垃圾数。 */
uint8_t hmc5883l_init(void);

/* hmc5883l_read：读三轴原始磁场（16 位有符号，已符号扩展）；出参可传 NULL
 * 表示不取该轴；返回 0=成功 1=读失败（无应答）。
 * ⚠️ 缺陷清单③：旧实现 data_l | (data_h << 8) 无符号扩展，负磁场读成 32768+
 * 的大正数。 */
uint8_t hmc5883l_read(int16_t *x, int16_t *y, int16_t *z);

/* hmc5883l_heading_from_xy：航向角纯函数（0–360°，顺时针；X 轴为 0°，
 * 即 heading = atan2(Y, X)，X 指向机头、Y 指向右侧时读数即罗盘方位角）。
 * 零向量返回 0（不产生 NaN）。独立暴露供单元测试直接调用——换算收敛于此
 * 一处。 */
float hmc5883l_heading_from_xy(float x, float y);

/* hmc5883l_read_heading：读三轴后出航向角（0–360°）；x_off/y_off = 硬铁
 * 偏移（现场磁干扰标定值，不校正传 0）；返回 0=成功 1=读失败。
 * 校准流程（8 字走位 / 椭球拟合）不入库（ADR 0009）——本接口只吃偏移量。 */
uint8_t hmc5883l_read_heading(float *deg, int16_t x_off, int16_t y_off);

#endif /* HMC5883L_H */
