/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《HX711称重传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/hx711-weighing-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef HX711_H
#define HX711_H

#include <stdint.h>

/* HX711 称重传感器驱动（mspm0，纯驱动切片，ADR 0009）：24 位 ADC 串行读取
 * （通道 A 增益 128）+ 去皮 + 克数换算。
 * 引脚 = 母版 syscfg 实例 HX711：SCK（输出，默认 PA28——与 jy61p / IMU601 /
 * sht30 / FINGERPRINT 默认脚重叠，同选时经引脚绑定消解）/ DT（输入，默认
 * PA31）。DT 挂内部上拉（模块空闲为高，数据准备好拉低）。
 * 时序协议（HX711 数据手册）：DT 拉低 = 转换完成 → 24 个 SCK 脉冲读 24 位
 * 数据（MSB 先）→ 第 25 个 SCK 脉冲选定通道 A + 增益 128。
 * gram 换算需要校准：HX711_GAP_VALUE 是「每克计数」被除数（立创实测 207.00，
 * 每只秤的传感器曲线不同，测试偏大则增大该值、偏小则减小）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--hx711-weighing-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 printf/main.c 演示、
 * 函数名规范化、引脚宏参数化、延时走 delay 模块）。 */

/* 校准参数：gram = (raw - tare) / HX711_GAP_VALUE（默认立创值 207.00） */
#define HX711_GAP_VALUE 207.00f

/* 本次没读到（driver-defect-fixes/03）：`hx711_read_raw()` 等 DT 就绪等满
 * 2 个转换周期（默认 10SPS ⇒ 200ms）仍未就绪时返回它，**不是 0**。
 * 为什么非要有这个值：合法读数是 `count ^ 0x800000`（24 位，0 ~ 0xFFFFFF），
 * 而 **0 既可能是「空秤零点」也可能是「没等到数据」**——拿 0 当失败标记就分不开
 * 这两种情况（0xFFFFFFFF 落在 24 位之外，不可能是合法读数）。 */
#define HX711_TIMEOUT_SENTINEL 0xFFFFFFFFu

/* hx711_init：初始化（SysConfig 已把 SCK 配输出、DT 配上拉输入，
 * 本函数先做一次去皮——空秤时开始，后续再调 hx711_tare 也安全）。
 * 这一次读**会等满一个转换周期**（默认 10SPS ⇒ 最多 ~100ms）：那是在等
 * 第一个样本，不是失败。 */
void hx711_init(void);

/* hx711_tare：去皮——把当前读数存为零点。初始化时秤上不要放东西。
 * **这一次读没读到（返回哨兵值）时零点原样不动**——绝不把哨兵当零点存进去
 * （那会让克数变成 raw + 1 的天文数字）。 */
void hx711_tare(void);

/* hx711_read_raw：读一次原始 24 位数据（通道 A 增益 128）。
 * 返回 = 计数（0 ~ 0xFFFFFF，空秤零点 ≈ 0x800000）；
 * **返回 `HX711_TIMEOUT_SENTINEL` = 本次没等到数据（不是读数）**。
 * 两次读之间天然隔着一个转换周期（默认 10SPS = 100ms）——驱动自己会等，
 * 调用方不必另加延时；零点参考见 hx711_tare。 */
uint32_t hx711_read_raw(void);

/* hx711_get_gram：读一次并换算为克数（float，含去皮）。
 * **返回负值 = 本次没读到**（-1.0f = 超时）；0.0f = 空秤 / 负重量钳 0。 */
float hx711_get_gram(void);

#endif /* HX711_H */
