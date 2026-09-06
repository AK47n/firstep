/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《SHT20温湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/sht20-temp-humi-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef SHT20_STM32_H
#define SHT20_STM32_H

#include <stdint.h>

/* SHT20 温湿度传感器驱动（stm32，纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设/TIMER），单次
 * 测量模式（no-hold，低功耗），读取温湿度并按换算公式出摄氏度 / 百分比
 * 相对湿度。API 与 mspm0 版完全对齐（sht20_init/read，同函数名/同语义/
 * 同返回码）。
 * 引脚 = pin_config.h 单源 SHT20_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——与 motor MOTOR_A_DIR/DIR2 默认重叠：温湿度与「带电机
 * 方向的小车运动控制」不同框、同选概率最低；**六件软 I2C 件默认共挂此总线**
 * （地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异——环境站合法共挂；**注意
 * pca9685 同址 0x40**：同总线双选 = 寻址冲突，须错开总线或改 pca9685 地址
 * 跳线——notes 提醒；页面默认 SDA=PB9/SCL=PB8 不采用 = 母版 OLED 段），
 * 同选时经引脚绑定消解。
 * 通信协议（SHT2x 数据手册 + 立创页面）：器件地址 0x40（写 0x80/读 0x81）；
 * 测量命令 0xF3 = 温度 no-hold 单次 / 0xF5 = 湿度 no-hold 单次（低功耗单次
 * 测量——与 sht30 周期模式 0x2130 分工）；最长测量 85ms（温度 14bit）/
 * 29ms（湿度 12bit）；回包 2 字节（14bit 左对齐 + 低 2 位状态位——物理计算
 * 前 & 0xFFFC 置 0，页面正文要求但页面代码未掩码，本驱动按手册修正）；页面
 * 无 CRC（「校验和可以不需要」——数据后发 NACK，照页面取舍）。
 * 换算（页面原式，0.01 系数口径）：温度 = raw/65536×175.72−46.85、
 * 湿度 = raw/65536×125−6。
 * ⚠️ 页面缺陷修正清单（全部 notes 记录 + 测试守卫防回潮）：
 *  ① do-while 裸轮询无上限（页面 L288-293——器件失联死等）→ 改
 *     ≤50×2ms 重试（100ms 窗口覆盖页面 85ms/29ms 最长测量）；
 *  ② 状态位未掩码（主缺陷）：正文「LSB 的后两位在进行物理计算前须置0」
 *     页面代码未 &0xFFFC → 修正（误差 <0.01℃/0.05%RH）；
 *  ③ 0xE3/0xE5（hold）注释 vs 0xF3/0xF5（no-hold）代码三方矛盾——正文
 *     L48+函数注释 L272-273 写 hold、代码+main 宏用 no-hold → 采信代码；
 *  ④ 写地址/命令应答失败仅 printf 后继续（无失败传播）→ 失败码 1/2；
 *  ⑤ char ack 死变量/类型宽度 → uint8_t 收敛。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--sht20-temp-humi-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * SHT20_Read → sht20_read（温度/湿度两段合并出参）、I2C 原语静态化、延时走
 * delay 模块、页面 2-6us 混合半周期归一为 5us（sht30 同款——mspm0 版同）。 */

#define SHT20_ADDR           0x40u /* SHT2x 固定地址（页面原式 0x80 写/0x81 读） */
#define SHT20_CMD_TEMP       0xF3u /* 温度测量（no-hold 单次，低功耗模式） */
#define SHT20_CMD_HUMI       0xF5u /* 湿度测量（no-hold 单次，低功耗模式） */
#define SHT20_READ_RETRY_MAX 50u   /* 读地址应答重试上限（页面最长测量 85ms，
                                    * ≤2ms×50 = 100ms 覆盖） */
#define SHT20_READ_RETRY_MS  2u

/* sht20_init：无器件初始化序列（单次测量模式无预置命令——页面 bsp 无 init，
 * 引脚配置由 init 内 gpio_init 完成），空实现占位。 */
void sht20_init(void);

/* sht20_read：完整读取温度 + 湿度两段（各 = 写地址 → 写测量命令 → 轮询读
 * 地址应答直到测量完成 → 读 2 字节 → NACK + 停止），返回 0 = 成功（出参
 * 有效：°C / %RH，分辨率 0.01 级——页面 ±0.3℃/±3%RH 精度档）、1 = 温度段
 * 测量失败（写地址/测量命令应答失败或读地址应答超时——页面 85ms 最长测量
 * 超出 100ms 重试窗口）、2 = 湿度段测量失败（同上；失败时出参不变）。
 * 出参判空用 0（F1 头无 NULL）。 */
uint8_t sht20_read(float *temperature_c, float *humidity_rh);

#endif /* SHT20_STM32_H */
