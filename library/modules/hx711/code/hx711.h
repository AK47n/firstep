#ifndef HX711_H
#define HX711_H

#include <stdint.h>

/* HX711 称重传感器驱动（mspm0，纯驱动切片，ADR 0009）：24 位 ADC 串行读取
 * （通道 A 增益 128）+ 去皮 + 克数换算。
 * 引脚 = 母版 syscfg 实例 HX711：SCK（输出，默认 PB24——与 step_motor RST2
 * 默认重叠，同选时经引脚绑定消解）/ DT（输入，默认 PB8——与 step_motor DCY2
 * 同脚）。DT 挂内部上拉（模块空闲为高，数据准备好拉低）。
 * 时序协议（HX711 数据手册）：DT 拉低 = 转换完成 → 24 个 SCK 脉冲读 24 位
 * 数据（MSB 先）→ 第 25 个 SCK 脉冲选定通道 A + 增益 128。
 * gram 换算需要校准：HX711_GAP_VALUE 是「每克计数」被除数（立创实测 207.00，
 * 每只秤的传感器曲线不同，测试偏大则增大该值、偏小则减小）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--hx711-weighing-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 printf/main.c 演示、
 * 函数名规范化、引脚宏参数化、延时走 delay 模块）。 */

/* 校准参数：gram = (raw - tare) / HX711_GAP_VALUE（默认立创值 207.00） */
#define HX711_GAP_VALUE 207.00f

/* hx711_init：初始化（SysConfig 已把 SCK 配输出、DT 配上拉输入，
 * 本函数先做一次去皮——空秤时开始，后续再调 hx711_tare 也安全）。 */
void hx711_init(void);

/* hx711_tare：去皮——把当前读数存为零点。初始化时秤上不要放东西。 */
void hx711_tare(void);

/* hx711_read_raw：读一次原始 24 位数据（通道 A 增益 128；0 = 转换失败超时）。
 * 单位 = 计数（约 1/g 量级，视传感器灵敏度），零点参考见 hx711_tare。 */
uint32_t hx711_read_raw(void);

/* hx711_get_gram：读一次并换算为克数（float，含去皮；raw 越界负值时返回 0）。 */
float hx711_get_gram(void);

#endif /* HX711_H */
