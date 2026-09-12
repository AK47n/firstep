/* 来源：QST（昆山东方微电子）QMC5883L 官方数据手册 QST-PD-B002-22
 * Rev. B《QMC5883L 三轴磁传感器》——https://www.qstcorp.com（3-Axis
 * Magnetic Sensor 器件页 PDF）。库内**无** lckfb 磁力计移植手册页
 * （地猛星 41 篇 / 地阔星 43 篇 sensor 页均无磁力计条目，已全库检索确认），
 * 故本件寄存器表依据 = 官方数据手册 + 仓库内既有 HMC5883L 实现
 * （库内与桌面工作目录遗留旧实现的缺陷清单）交叉核对。
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、引脚宏参数化等）。 */

#ifndef QMC5883L_H
#define QMC5883L_H

#include <stdint.h>

/* QMC5883L 三轴磁力计 / 电子罗盘驱动（mspm0，纯驱动切片，ADR 0009）：
 * - 软 I2C 位操作读取（不占硬件 I2C 外设，SDA 方向运行时切换，照 bh1750）；
 * - 与 hmc5883l 模块**同名同语义 API**（init/read/read_heading）：换芯片只
 *   改头文件名与引脚宏。⚠️ 两者寄存器表完全不同，**不可混用初始化序列**：
 *   0x09 在 HMC 是状态寄存器（SR）、在 QMC 是控制1；0x0B 在 HMC 是 ID 尾字节
 *   （IRC）、在 QMC 是 SET/RESET 周期——把 HMC 的初始化序列（CRA/CRB/MR）
 *   发给 QMC 会写坏它的控制字（0x09 被写成模式/速率字、0x0B 被写成周期值），
 *   器件从此读出的不是磁场数据；
 * - 一次读数：qmc5883l_init（软复位 → Chip ID 校验 → 控制字配置）→
 *   qmc5883l_read（等状态寄存器 DRDY → 读 0x00..0x05 六字节 → 小端 16 位
 *   有符号拼装）→ qmc5883l_read_heading（atan2f 出 0–360° 航向，可传硬铁
 *   偏移）。 */
#define QMC5883L_CHIP_ID 0xFFu /* Chip ID 寄存器（0x0D）应读回值 */

#define QMC5883L_ADDR_WRITE 0x0Du /* 7 位地址 0x0D<<1|0 = 0x1A（手册表 10） */
#define QMC5883L_ADDR_READ 0x0Eu  /* 7 位地址 0x0D<<1|1 = 0x1B（手册表 11） */

/* 寄存器地址（手册 Rev. B §9.1 寄存器表 Table 12——0x0D 既是 Chip ID 寄存器
 * 地址、又是写入阶段的从机地址字，两者同值不冲突：位置不同） */
#define QMC5883L_REG_DATA 0x00u   /* 数据段 0x00..0x05：X/Y/Z 各 16 位小端 */
#define QMC5883L_REG_STATUS 0x06u /* 状态：bit0 DRDY / bit1 OVL / bit2 DOR */
#define QMC5883L_REG_CTRL1 0x09u  /* 控制1：OSR[7:6]/RNG[5:4]/ODR[3:2]/MODE[1:0] */
#define QMC5883L_REG_CTRL2 0x0Au  /* 控制2：SOFT_RST[7]/ROL_PNT[6]/INT_ENB[0] */
#define QMC5883L_REG_FBR 0x0Bu    /* SET/RESET 周期：手册推荐写 0x01 */
#define QMC5883L_REG_CHIP_ID 0x0Du /* Chip ID：手册明示读回 0xFF */

/* 状态寄存器位（手册 Rev. B 表 14） */
#define QMC5883L_STATUS_DRDY 0x01u /* bit0：新数据就绪 */
#define QMC5883L_STATUS_OVL 0x02u  /* bit1：任一轴溢出（本件不用，供用户判饱和） */
#define QMC5883L_STATUS_DOR 0x04u  /* bit2：数据被跳读（本件不用） */

/* 控制寄存器常量（手册 Rev. B 表 16/17/18） */
#define QMC5883L_CTRL2_VALUE 0x40u /* bit7 SOFT_RST=0（不软复位——复位只走
                                    * init 起手的显式 0x80 路径）、bit6
                                    * ROL_PNT=1（开指针翻转，0x00~0x06 连续读
                                    * 一次取齐）、bit0 INT_ENB=0（不开中断脚） */
#define QMC5883L_CTRL2_RESET 0x80u    /* bit7 = SOFT_RST：恢复全部寄存器默认值
                                       * （默认 MODE=Standby） */
#define QMC5883L_FBR_PERIOD 0x01u /* SET/RESET 周期推荐值（手册 §9.2.5 原话） */
#define QMC5883L_CTRL1_VALUE 0x1Du /* OSR=512 | RNG=±8G | ODR=10Hz | MODE=连续
                                    * （逐位：bit7:6 OSR=00=512、bit5:4 RNG=01=
                                    * ±8G、bit3:2 ODR=11=10Hz、bit1:0 MODE=01=
                                    * 连续测量） */
/* 数据就绪等待与复位等待（单位 ms；delay 模块） */
#define QMC5883L_DRDY_TIMEOUT_MS 20u /* 10Hz ODR 下 DRDY 周期 ~100ms；取值 =
                                   * 20×1ms 轮询——手册给含 0x00 的写序列（非
                                   * 无重复起点）留 1ms 级余量，真机若不足调大 */
#define QMC5883L_RESET_WAIT_MS 10u   /* 软复位后等器件进 Standby 再验 ID */

/* 数据寄存器 / 状态寄存器读出的字节数（1 次连续读） */
#define QMC5883L_DATA_LEN 6u

/* qmc5883l_init：软复位（CTRL2←0x80）→ 等 QMC5883L_RESET_WAIT_MS →
 * 读 Chip ID 校验 → 写 SET/RESET 周期（0x0B←0x01）→ 写控制1（0x09←0x1D）
 * → 写控制2（0x0A←0x40）。
 * 返回 0 = 成功、1 = 总线无应答/通信失败、2 = 器件 ID 不符（0x0D 读回不为
 * QMC5883L_CHIP_ID——多为把 QMC 当 HMC 接、或器件没接/型号不符）。 */
uint8_t qmc5883l_init(void);

/* qmc5883l_read：等状态寄存器 DRDY（0x06 bit0，超时 QMC5883L_DRDY_TIMEOUT_MS
 * 后仍按现状读一次）→ 连续读 0x00..0x05 六字节（指针翻转使能，一次读全）。
 * 三轴原始值 = 16 位**小端有符号**（低字节在前，已符号扩展）；
 * 返回 0 = 成功、1 = 读失败（总线无应答）；出参失败时保持原值。 */
uint8_t qmc5883l_read(int16_t *x, int16_t *y, int16_t *z);

/* qmc5883l_read_heading：读三轴 → 航向角（0–360°，顺时针；x_off/y_off 为
 * 硬铁偏移原始值，传 0 即不校正）。z 不入航向公式（航向只用 x/y）。
 * 返回 0 = 成功、1 = 读失败；出参失败时保持原值。 */
uint8_t qmc5883l_read_heading(float *deg, int16_t x_off, int16_t y_off);

/* qmc5883l_heading_from_xy：航向换算纯函数（无 IO，可单测；模块内换算唯一
 * 收敛点）。入参 = 已减偏移的 x/y 原始值，出参 = 0–360° 顺时针航向（与
 * 传感器 xy 平面对齐：+X 指「前/北」、+Y 指「右/东」为 90°）。
 * 零向量（x=y=0，含 -0.0 形式）返回 0，不产生 NaN。 */
float qmc5883l_heading_from_xy(float x, float y);

#endif /* QMC5883L_H */
