/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《HX711称重传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/hx711-weighing-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef HX711_STM32_H
#define HX711_STM32_H

#include <stdint.h>

/* HX711 称重传感器驱动（stm32，纯驱动切片，ADR 0009）：24 位 ADC 串行读取
 * （GPIO 双线 SCK/DT，非 I2C——通道 A 增益 128）+ 去皮 + 克数换算。
 * API 与 mspm0 版完全对齐（同函数名/同签名/同语义/同出参单位）。
 * 引脚 = pin_config.h 单源 HX711_SCK_GPIO/_SCK_PIN/_DT_GPIO/_DT_PIN
 * （默认 SCK=PB5 / DT=PB0——PB5 叠 MOTOR_A_ENC（光电编码器闭环小车与静态
 * 称重/电子秤不同框）；PB0 叠 MOTOR_B_DIR（TB6612 B 相方向与称重不同框）；
 * 刻意不叠本批 I2C 件与采集类（flame/ir_beam/human_ir 等——称重+传感站
 * 常见组合）与声光件；页面默认 SCK=PB8/DT=PB9 不采用 = OLED 段（称重×OLED
 * 显示是电子秤最标准组合，同选概率最高）；同选经引脚绑定消解）。
 * 时序协议（HX711 数据手册）：DT 拉低 = 转换完成 → 24 个 SCK 脉冲读 24 位
 * 数据（MSB 先）→ 第 25 个 SCK 脉冲选定通道 A + 增益 128。
 * **页面缺陷修正清单（notes + 守卫）**：① **`while(DT_GET());` 无界轮询
 * （主缺陷）**——拆机/未接传感器死等 → **20ms 超时**（2000×10us，超时返回
 * 0=失败，mspm0 先例）；② 全局泄漏（HX711_Buffer/Weight_Maopi/
 * Weight_Shiwu/Flag_Error 死变量）→ 收敛模块内 static s_tare；③ **GapValue
 * 207.00 演示校准常数** → 参数化宏 HX711_GAP_VALUE（每只秤实测调整）；④
 * 24bit 补码 `^0x800000` 转无符号偏移量（mspm0 同款——负值钳 0 约定）；
 * ⑤ 页面「查看资料」节空（不提炼）。 */
/* 校准参数：gram = (raw - tare) / HX711_GAP_VALUE（默认立创值 207.00——
 * 每克计数被除数；测试偏大则增大该值、偏小则减小——页面注释同口径） */
#define HX711_GAP_VALUE 207.00f

/* hx711_init：引脚配置（SCK 输出 PP、DT 上拉输入 IU——页面先 PP 输出再重配
 * IPU 的动作按 mspm0 先例收敛，模块自管方向）+ 先做一次去皮——空秤时开始，
 * 后续再调 hx711_tare 也安全。 */
void hx711_init(void);

/* hx711_tare：去皮——把当前读数存为零点。初始化时秤上不要放东西。 */
void hx711_tare(void);

/* hx711_read_raw：读一次原始 24 位数据（通道 A 增益 128；0 = 转换失败超时
 * ——页面无界轮询修正：20ms 超时）。单位 = 计数（约 1/g 量级，视传感器
 * 灵敏度），零点参考见 hx711_tare。 */
uint32_t hx711_read_raw(void);

/* hx711_get_gram：读一次并换算为克数（float，含去皮；raw 越界负值时返回 0）。 */
float hx711_get_gram(void);

#endif /* HX711_STM32_H */
