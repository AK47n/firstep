/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《DHT11温湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/dht11.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef DHT11_STM32_H
#define DHT11_STM32_H

#include <stdint.h>

/* DHT11 数字温湿度传感器驱动（stm32，纯驱动切片，ADR 0009）：
 * - 单总线位时序：一根数据线双向（主机拉低 ≥18ms 起始 → 模块响应 →
 *   40bit 数据（高位先出）→ 校验和；位 0/1 按高电平时长区分）；
 * - 数据线方向运行时切换（DHT11_DATA_OUT/IN 宏，照 AHT10_SDA 先例），
 *   模块板自带 4.7k~10k 上拉；空闲时总线保持高电平；
 * - 微秒/毫秒延时走库内 delay 模块，CPU 忙等位时序，不占 TIMER
 *   （sr04 先例——页面 delay_uus 页外工具函数替换为 delay_us）；
 * - 校验和失败或应答超时 → dht11_read 返回 1（0 = 成功——**页面返回语义
 *   混用（0=失败/非 0=数据）修正**，mspm0 批 2 同款）；
 * - API 与 mspm0 版完全对齐（dht11_init/read/read_temperature/
 *   read_humidity，同函数名/同语义/同返回码 0=成功 1=失败）。
 * 引脚 = pin_config.h 单源 DHT11_GPIO/DHT11_PIN（默认 **PB3**——与
 * key.KEY_START（按键）+ pid.GRAY_D6（巡线灰度）默认重叠：环境件与独立
 * 按键/巡线不同框、同选概率最低；刻意不叠声光/显示/传感站组合——温湿度+
 * 声光/显示为常见搭配；单总线件与软 I2C 总线件（PA6/PA7）不共脚；页面
 * 默认 PB0 不采用 = MOTOR_B_DIR（母版 TB6612 B 相方向），同选经引脚绑定
 * 消解）。
 * 通信协议（页面资料 + DHT11 数据手册）：60s 测量周期（建议采样间隔 ≥2s
 * ——器件自发热/湿度响应慢，归调用方）；起始低电平 ≥18ms（19ms）→ 释放
 * 高 → 模块响应 80us 低 + 80us 准备 → 40bit（湿整+湿小+温整+温小+校验和，
 * 高位先出）→ 结束 54us 低后转输入释放总线；位 0 = 54us 低 + 27us 高、
 * 位 1 = 54us 低 + 74us 高——只以高电平时长区分（分界 CHECK_TIME 28us）；
 * 校验 = 前 4 字节之和末 8 位 == 第 5 字节；换算 0.1 系数（湿度=整+小×0.1
 * %RH、温度=整+小×0.1 ℃）；规格 湿度 20-90%RH ±5%、温度 0-50℃ ±2℃、
 * 分辨率 8bit。
 * ⚠️ 页面缺陷修正清单（全部 notes 记录 + 测试守卫防回潮）：
 *  ① 响应/位等待超时无错误汇报（页面 L270-296——坏线仍读 40bit 垃圾）→
 *     无应答/回应超时立即返回 1（位循环超时由校验和兜底——可接受）；
 *  ② 返回语义归一（页面 0=失败/非 0=数据 → 库内 aht10 惯例 0=成功/1=失败）；
 *  ③ delay_uus 页外工具函数 → delay_us（页面片段 L77 vs 正式 c L285 不一
 *     致，formal 版 delay_us 采信）；
 *  ④ RCU_DHT11 未用宏不落（页面 .c 直接 RCC_APB2Periph_GPIOB——宏未用）；
 *  ⑤ extern float temperature/humidity 全局泄漏 → static 缓存 + 出参；
 *  ⑥ CHECK_TIME 28us 与位超时 80 步进保留立创原值；时间轴常量单源本头。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/sensor--dht11.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化（DHT11_Read_Data→dht11_read、Get_temperature/Get_humidity→
 * read_temperature/read_humidity）、全局温湿度缓存改出参、I2C 原语族
 * 静态化、延时走 delay 模块）。 */

/* ---------- 位时序时间轴（页面原值；源码只引用常量，不散写字面量） ---------- */

#define DHT11_START_MS      19u  /* 起始信号：低电平 ≥18ms（立创 bsp 用 19ms） */
#define DHT11_RELEASE_US    20u  /* 释放总线后等待（页面 20us） */
#define DHT11_CHECK_TIME_US 28u  /* 0/1 码位高电平时长分界（0 码 27us < 28us） */
#define DHT11_WAIT_US       80u  /* 响应/位等待超时步进数（1us/步，立创 bsp 原值） */
#define DHT11_BIT0_LOW_US   54u  /* 位 0/1 共同低电平时长（页面 54us） */
#define DHT11_BIT0_HIGH_US  27u  /* 位 0 高电平时长（< 28us 分界） */
#define DHT11_BIT1_HIGH_US  74u  /* 位 1 高电平时长（> 28us 分界） */

/* dht11_init：单脚初始化为输出 + 总线空闲高电平（模块数据线空闲要求，
 * 模块板自带 4.7k~10k 上拉——空闲必须高电平）。 */
void dht11_init(void);

/* dht11_read：一次完整测量——内部完成起始/响应/40bit 接收/校验/换算。
 * 出参 temperature_c（℃）/ humidity_rh（%RH）；返回 0=成功 1=失败
 * （校验和不符或无应答/回应超时——出参保持原值不变）。 */
uint8_t dht11_read(float *temperature_c, float *humidity_rh);

/* dht11_read_temperature / dht11_read_humidity：返回最近一次成功读数缓存
 * （手册 Get_temperature/Get_humidity 语义：不触发新测量；失败/未读时缓存
 * 保持上次值，从未成功 = 0.0f）。 */
float dht11_read_temperature(void);
float dht11_read_humidity(void);

#endif /* DHT11_STM32_H */
