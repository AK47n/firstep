/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《GP2Y1014AU粉尘传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/gp2y1014au-dust-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef GP2Y1014AU_STM32_H
#define GP2Y1014AU_STM32_H

#include <stdint.h>

/* GP2Y1014AU 粉尘传感器驱动（stm32 纯驱动薄封装，ADR 0009）：
 * - ADC 薄封装：通道 = 母版 pin_config.h 单源 GP2Y1014_AO_CH（默认
 *   ADC_Channel_5 = PA5——页面原脚；本批 8 件与 flame 共读 PA5，同一物理
 *   脚只能接一件器件——多件同测需外部分路器/分时切换）+ **LED 驱动 GPIO
 *   输出（器件必需例外）**：GP2Y1014AU 内置红外 LED 必须由主控按页面时序
 *   脉冲驱动（LED 亮 → 280us → 采样 → 40us → LED 关 → 9680us，周期 10ms）
 *   才能测量，无此脚传感器不工作——薄封装仅指 ADC 部分；
 * - 换算 f = 0.17×value − 0.1（页面 Read_dust_concentration 原式——
 *   相对估算非精标：页面公式对演示值/ADC 量程标定不明确）；**页面 SAMPLES
 *   30 × 2ms ≈ 62ms 采样跨 LED 关断、时序本就不自洽** → 5 次快平均
 *   （us016/mspm0 先例，单次读回到 ~0.3ms 级）；
 * - 页面 Filter（10 点静态滑动平均）内嵌为模块内 static 环形缓冲（页面
 *   滤波逻辑简单——照库依赖先例取舍不依赖库内 filter 可选配套件）；
 * - 轮询读取（无 ADC 中断——模块 API 忙等单点实现）；
 * - LED 默认脚 = **PB5**（页面原脚 PA2 = DEBUG_UART TX 常备件不照抄——
 *   PB5 叠 hx711 SCK + MOTOR_A_ENC，粉尘与称重/编码器闭环不同框）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--gp2y1014au-dust-sensor.md
 * （立创 wiki 地阔星移植手册；页面无资料下载链接（仅移植成功案例）；
 * 代码按模块库规范改写：去 main/printf、函数名规范化、页面 ADC 序列收敛
 * ml_adc、页面 SAMPLES 30×2ms 改 5 次快平均、页面 stdio.h 残余剔除、
 * Filter 全局符号收敛 static）。 */

/* 快速平均采样次数（页面 SAMPLES 30 次 × 2ms ≈ 62ms——远超 10ms LED 脉冲
 * 周期，页面时序本就不自洽；us016 快平均先例改 5 次，单次读回到 ~0.3ms 级） */
#define GP2Y1014_ADC_SAMPLES 5u

/* 页面 Filter 滑动平均窗口（10 值环形缓冲——首次调用以首值填满窗口） */
#define GP2Y1014_FILTER_WINDOW 10u

/* LED 脉冲时序（页面 Read_dust_concentration 原值——10ms 采样周期）：
 * LED 亮 → 280us 电压建立/采样点 → 采样 → 40us → LED 关 → 9680us 尾段 */
#define GP2Y1014_LED_SETTLE_US 280u
#define GP2Y1014_LED_SAMPLE_TAIL_US 40u
#define GP2Y1014_LED_CYCLE_TAIL_US 9680u

/* gp2y1014_init：LED 推挽输出 + 空闲 = 关（引脚高）+ 初始化 ADC1 对应通道。 */
void gp2y1014_init(void);

/* gp2y1014_read_dust：按页面 LED 脉冲时序采样并返回粉尘浓度**估算值**
 * （页面原式 0.17×value − 0.1——相对参考值非精标：红外漫反射对烟尘/水汽
 *  同样响应（烟/尘区分不能），绝对浓度需标准粉尘标定；调用间隔 ≥ 10ms
 *  （LED 周期），连续读时勿快于周期）。 */
float gp2y1014_read_dust(void);

#endif /* GP2Y1014AU_STM32_H */
