/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《雨滴传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/rain-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef RAIN_H
#define RAIN_H

#include <stdint.h>

/* 雨滴传感器驱动（mspm0 纯驱动薄封装，ADR 0009）：
 * - 薄封装：依赖库内 adc 模块读 ADC12_0 MEM0（adc_get(ADC_1, ADC_Channel_0)），
 *   不新开 ADC 通道——与 adc/us016/mq2 共享 MEM0 槽位（默认 PA24/A0_3）；
 * - 分压电压 → 雨量百分比：percent = value/4095×100（**正向映射**——雨越大
 *   百分比越高；页面原式为 (1 − value/4095)×100，与页面正文「雨水越大，电阻
 *   值越小，模拟值转化为的数字值越大」矛盾（照原式雨越大百分比反而越低），
 *   按正文取证修正为正向映射——见 notes）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 3 次 × 100ms 间隔，按 us016 快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--rain-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、DO 数字量阈值未声明——页面 GET_DO 仅宏未使用）。 */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值 */
#define RAIN_ADC_MAX 4095u

/* 快速平均采样次数（页面 3 次 × 100ms 间隔，us016 快平均先例改 5 次） */
#define RAIN_ADC_SAMPLES 5u

/* rain_init：使能 ADC12_0 转换（薄封装——adc_init 即 MEM0 轮询初始化）。 */
void rain_init(void);

/* rain_read_percent：读 AO 分压对应的雨量百分比（0-100% 相对值——**正向
 * 映射**：雨越大百分比越高（页面正文「雨水越大→ADC 值越大」）；相对值非
 * 绝对值——雨滴板脏污/氧化/放置方式改变基线电阻，「值对应降雨量多少毫米需
 * 实体测量」（页面原话）；若实物分压方向相反改公式一处即可）。 */
float rain_read_percent(void);

#endif /* RAIN_H */
