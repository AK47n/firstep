/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AGS10有害气体传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ags10-harmful-gas-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef AGS10_STM32_H
#define AGS10_STM32_H

#include <stdint.h>

/* AGS10 有害气体传感器驱动（stm32，纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设/TIMER），读取
 * TVOC 浓度（ppb）。API 与 mspm0 版完全对齐（ags10_init/read，同函数名/
 * 同语义/同返回码）。
 * 引脚 = pin_config.h 单源 AGS10_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——与 motor MOTOR_A_DIR/DIR2 默认重叠：有害气体传感与「带
 * 电机方向的小车运动控制」不同框、同选概率最低；**六件软 I2C 件默认共挂
 * 此总线**（地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异——空气质量站合法共挂；
 * 页面默认 SDA=PB8/SCL=PB9 不采用 = 母版 OLED 段），同选时经引脚绑定消解。
 * 通信协议（AGS10 数据手册 + 立创页面）：器件地址 0x1A（写 0x34/读 0x35）；
 * 读 TVOC：写寄存器 0x00 → 读 5 字节回包 = 状态 + TVOC 24bit（data[1..3]）+
 * CRC（data[4]，CRC8 初值 0xFF/多项式 0x31——页面 Calc_CRC8 原式）；
 * 页面规格 I2C ≤15kHz 与页面代码时序（半周期 5us ≈ 100kHz）不一致——按
 * 页面代码实现，真机通信异常时按规格调慢半周期（见 ags10_stm32.c 注释）。
 * ⚠️ 页面缺陷修正清单（全批最重，全部 notes 记录 + 测试守卫防回潮）：
 *  ① **读地址重试条件写反（致命）**：页面 L280
 *     `while((WaitAck()==1) && (timeout >= 50))`——首轮后 timeout=1、
 *     条件恒假 → 循环一次即退、L283 `if(timeout >= 50) return 3` 永不触发
 *     （与函数注释「3：等待超时」矛盾）→ 修正 `timeout < AGS10_RETRY_MAX`
 *     （ir_remote/nrf24l01 上游缺陷先例，mspm0 版已同）；
 *  ② **返回码与 TVOC 值混用**：页面 ags10_read 主返回 = TVOC 值或错误码
 *     1-4（TVOC=1ppb 与「通信失败」不可分）→ 出参 + 状态码（mlx90614 先例）；
 *  ③ **delay_1us/delay_1ms 库内不存在**（ml_delay.h 仅 delay_us/ms/s）
 *     → delay_us(5)/delay_ms(1)/delay_ms(1000) 换算；
 *  ④ **规格 ≤15kHz vs 代码 ≈100kHz 矛盾**（差 ~7 倍——按页面代码实现，
 *     真机通信异常时调慢 SCL 半周期（唯一时序宏点））；
 *  ⑤ 注释掉的调试 printf（Check failed）——不落；⑥ char ack 死变量收敛；
 *  ⑦ Send_Nack/Send_Ack 冗余二次写（末值正确——页面原式保留）；
 *  ⑧ main 未等预热 ≥120s + 1s 采样 <2s 规格（演示——不落，预热归调用方）；
 *  ⑨ 状态字 data[0] 未使用（页面未说明状态位——读入不检查）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--ags10-harmful-gas-sensor.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化、IIC 原语族静态化、页面返回值收敛为出参 + 状态码、页面
 * 读地址重试条件写反按函数注释语义修正）。 */

#define AGS10_ADDR 0x1Au /* 7bit 地址（页面 0x34 写/0x35 读 = 0x1A<<1 | 0/1） */
#define AGS10_REG_TVOC 0x00u /* 读 TVOC 数据寄存器（页面写值） */
#define AGS10_RETRY_MAX 50u  /* 读地址应答重试上限（页面 ≤50×1ms） */

/* ags10_init：空实现占位——AGS10 无独立初始化序列（页面演示直接读；
 * 预热 ≥120s 期间读数起步，属器件特性，等待归调用方）；引脚配置由 init
 * 内 gpio_init 完成（页面 ags10_gpio_init 原式：OD + 两脚置高）。 */
void ags10_init(void);

/* ags10_read：读 TVOC 浓度（ppb；0-99999 量程，25℃/50%RH 典型精度 25% 读数，
 * 采样周期 ≥2s、预热 ≥120s）。
 * 返回 0 = 成功（voc_ppb 出参带回——判空用 0，F1 头无 NULL）；1 = 通信失败
 * （写地址应答）；2 = 发送失败（寄存器字节应答）；3 = 等待超时（读地址
 * >50×1ms 无应答）；4 = CRC 校验失败（页面失败码语义——页面返回值与
 * TVOC 值混用已收敛为出参 + 状态，mlx90614 先例）。 */
uint8_t ags10_read(uint32_t *voc_ppb);

#endif /* AGS10_STM32_H */
