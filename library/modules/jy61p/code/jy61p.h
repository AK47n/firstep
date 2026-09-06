#ifndef JY61P_H
#define JY61P_H

#include <stdint.h>

/* JY61P 六轴姿态传感器驱动（mspm0，纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，不占硬件 I2C 外设/TIMER；页面 12Pin 模块 IIC 控制方式，
 * 默认 9600 串口为备选未用——本件按页面 IIC 例程），器件内卡尔曼融合直接
 * 输出三轴角度（横滚/俯仰/航向，±180°），读角度无需主控端融合。
 * 引脚 = 母版 syscfg 实例 JY61P：SCL（输出，默认 PA28——与 IMU601/FINGERPRINT
 * UART/HX711/SHT30/MICROWAVE 默认重叠，同选时经引脚绑定消解）/ SDA（双向，
 * 默认 PA31——同上）。SDA 方向运行时切换（写 = 输出，读 ACK/数据 = 输入）。
 * 通信协议（WitMotion 寄存器表 + 立创页面）：器件地址 0x50（写 0xA0/读 0xA1）；
 * 寄存器：0x69 寄存器写使能（写 {0x88, 0xB5}）、0x01 角度参考（0x04,0x00 = Z 轴归零 /
 * 0x08,0x00 = 角度归零）、0x00 保存；角度寄存器 0x3D 起 6 字节
 * （Roll 低/高、Pitch 低/高、Yaw 低/高——LSB 先）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--jy61p-measurement-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * get_angle 按库风格重命名 jy61p_read_angles（出参）、页外 Gyro_Structure
 * 全局收敛为出参、writeDataJy61p 私有化为寄存器写原语、IIC 原语静态化、
 * 延时走 delay 模块；页面 I2C_WaitAck 未在采样前拉高 SCL 的时序微瑕按
 * sht20/sht30 正确版实现——行为等价、页面真机可用的记录见 manifest notes）。 */

#define JY61P_ADDR           0x50u /* 页面设备地址（0xA0 写 / 0xA1 读） */
#define JY61P_REG_UN         0x69u /* 寄存器写使能（写 {0x88,0xB5}） */
#define JY61P_REG_SAVE       0x00u /* 保存寄存器（写 {0x00,0x00}） */
#define JY61P_REG_ANGLE_REFER 0x01u /* 角度参考寄存器（0x04,0x00 Z 轴归零 /
                                     * 0x08,0x00 角度归零） */
#define JY61P_REG_ROLL_LOW   0x3Du /* 角度寄存器 0x3D 起 6 字节（页面读 0x3D） */
#define JY61P_ANGLE_BYTES    6u    /* Roll/Pitch/Yaw 各 2 字节（LSB 先） */
#define JY61P_INIT_DELAY_MS  200u  /* 页面实验值（官方建议 3s，200ms 够用） */

/* jy61p_init：器件初始化序列（页面 jy61pInit 原样）——Z 轴归零 + 角度归零
 * 两轮（每轮 = 寄存器写使能 → 写参考寄存器 → 保存，各步 200ms）——初始化后
 * 模块以当前姿态为参考零位。约 1.2s 阻塞（6×200ms 页面实验值）。 */
void jy61p_init(void);

/* jy61p_read_angles：读三轴角度（页面 get_angle 换算保留）——读 0x3D 起
 * 6 字节，raw/32768.0×180.0 换算 + ±180° 回绕（>180 减 360、<−180 加 360，
 * 页面原式），出参为度（float）；返回 0 = 成功（出参有效）、1 = 读写应答
 * 失败（出参不变）。 */
uint8_t jy61p_read_angles(float *roll_deg, float *pitch_deg, float *yaw_deg);

/* jy61p_read_raw：原始数据读取（页面 readDataJy61p 形态）——读 0x3D 起
 * 6 字节原始角度数据（LSB 先，未经换算），供自定义换算/调试；
 * 返回 0 = 成功、1 = 读写应答失败。 */
uint8_t jy61p_read_raw(uint8_t data[JY61P_ANGLE_BYTES]);

#endif /* JY61P_H */
