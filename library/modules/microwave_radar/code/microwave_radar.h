/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《微波多普勒无线雷达传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/microwave-doppler-radar-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef MICROWAVE_RADAR_H
#define MICROWAVE_RADAR_H

#include <stdint.h>

/* HB100 微波多普勒雷达模块驱动（mspm0，纯驱动切片，ADR 0009）：1 × GPIO
 * 输入（内部上拉），microwave_radar_read() 返回 1=检测到移动、0=无移动。
 * 引脚 = 母版 syscfg 实例 MICROWAVE：OUT（输入 + 内部上拉，默认 PA31——与
 * IMU601 RX（姿态）/HX711 DT（称重）/FINGERPRINT_UART RX（身份）/SHT30 SDA
 * （温湿度）重叠：微波雷达（自动门/车流/倒车）与姿态/称重/身份/温湿度采集
 * 不同框、同选概率最低（2026-09-06 SysConfig CLI 实证 PA0/PA1 不在 GPIO 输入
 * 实例 pin 选项内——原拟 PA0 板载 LED 指示作废，改选 PA31）；与同批
 * human_ir（PB8）刻意错开（人体红外+微波组合常同选，默认即不撞）；同选时
 * 经引脚绑定消解）。
 * 极性（按页面，自一致）：页面函数注释 + main 演示均按「检测到物体移动 =
 * OUT 低电平」（判移动按 OUT 输入为 0；0=检测到、1=未检测到）
 * ——默认沿用页面；实物输出反相时把 MICROWAVE_TRIGGER_LEVEL 改为 1 即可
 * 反相，其余零改动（单点反相宏，TTP224_TOUCH_LEVEL 先例）。
 * 模块特性（页面说明）：多普勒原理检测**物体运动**（不局限于人体、不受
 * 环境温度影响、探测距离 2-16m 连续可调、5V±0.25V 供电、30-50mA）；页面
 * main 演示的开/关门时序逻辑（flag/time、2000ms 关门）归生成骨架
 * （ADR 0009——模块只出 init/read）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--microwave-doppler-radar-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf/演示
 * 时序、页面 OUTPIN_Scanf/OUT_IN 宏收敛为 init/read + 极性单宏）。 */

/* 检测判定电平（单点反相宏）：0 = 引脚低 = 检测到移动（页面注释+演示，
 * 页面原样）；1 = 引脚高 = 检测到移动（实物输出反相时改此宏，其余零改动）。 */
#define MICROWAVE_TRIGGER_LEVEL 0u

/* microwave_radar_init：GPIO 输入由 SYSCFG_DL_init() 配置（内部上拉），空实现
 * 占位保持 API 一致（ttp224/ir_beam 先例）。 */
void microwave_radar_init(void);

/* microwave_radar_read：读检测状态。返回 1 = 检测到物体移动、0 = 无移动
 * （按 MICROWAVE_TRIGGER_LEVEL 极性；电平直读无去抖/无 GPIO 中断——GROUP1
 * 仍被 motor 编码器独占，页面同为电平直读，骨架侧按需滤波；注意只对运动
 * 物体敏感，静止人体不触发）。 */
uint8_t microwave_radar_read(void);

#endif /* MICROWAVE_RADAR_H */
