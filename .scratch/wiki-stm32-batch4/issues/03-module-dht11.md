# 03 — dht11 温湿度传感器（单总线位时序，手册 sensor--dht11.md）

**要做什么：** 模块库 `dht11` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼单总线驱动为纯驱动切片（单 GPIO 双向：发送=gpio_init OUT_PP、读位=gpio_init IU + gpio_get，方向运行时重配；忙等 delay_us——不占 TIMER/不注册中断），API 与 mspm0 版完全对齐：`dht11_init()`（单脚初始化为输出+总线空闲高）+ `dht11_read(float *temperature_c, float *humidity_rh)`（**0=成功/1=超时**——页面返回语义混用（0=失败/非 0=数据）修正；40bit = 湿整+湿小+温整+温小+校验和）+ `dht11_read_temperature()/read_humidity()`（返回最近一次成功读数缓存——失败/未读保持上次值，mspm0 语义）。

**关键事实（已取证，%TEMP%\batch4-facts.md）：** F1；页面默认 DATA=PB0（不照抄——本件默认 **PB3**，叠 KEY+GRAY_D6：环境件与独立按键/巡线不同框；刻意不叠声光/显示/传感站组合——温湿度+声光/显示为常见搭配）。时序：19ms 起始信号（页面 18-20ms）、响应 80us+80us、位 0/1=54us 低+27/74us 高、采样 CHECK_TIME 28us、`delay_uus` 页外函数 → delay_us；0.1 系数（温度/湿度整数+1 位小数）；校验 = 前 4 字节和末 8 位 == 第 5 字节。

**页面缺陷（修正+notes+守卫）：** ① 响应/位等待超时无错误汇报 L270-296（坏线仍读 40bit 垃圾）→ 超时返回 1；② 返回语义归一（0=成功）；③ delay_uus 页外 → delay_us；④ RCU_DHT11 未用宏不落；⑤ extern 全局泄漏收敛模块内 static；⑥ 采样节拍（≥2s 间隔）归调用方 notes。

**引脚与默认脚：** pins `DHT11_DATA`（type `gpio_out`——对偶 mspm0 系统语义（方向运行时切换），default **PB3**，macros `[DHT11_GPIO, DHT11_PIN]`）；pin_config.h 宏段：`#define DHT11_GPIO GPIO_B` / `#define DHT11_PIN Pin_3`（注释：默认 PB3 叠 KEY+GRAY_D6——环境件与按键/巡线不同框；同选经绑定消解；PB3 现 2 角色三叠登记）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/dht11/code/dht11_stm32.c/.h`（独立 stm32 头；.c gpio_init/gpio_set/gpio_get + delay_us；方向切换宏 `DHT11_OUT()/IN()`——落地为 DHT11_DATA_OUT()/IN()；零引脚字面量/零标准库）
- [x] init：gpio_init(DHT11_GPIO, DHT11_PIN, OUT_PP) + gpio_set(1)（空闲高）；超时保护（响应等待各带计数上限 80 步，超时返回 1）
- [x] 时间轴常量 .h 单源（19ms/28us/54us/27us/74us/80 宏——照 mspm0 .h 口径）
- [x] manifest.json platforms 增 stm32：files `[code/dht11_stm32.c, code/dht11_stm32.h]`、dependencies ["delay"]、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/dht11.html`）、notes（手册路径+原页+网盘+缺陷 5 条+超时保护+返回语义+默认脚推理+采样间隔归调用方+未上板）
- [x] pin_config.h 增 2 宏
- [x] 测试 `tests/test_module_dht11.py`：形状+宏存在+单选生成全流程+mspm0 零改动守卫+守卫（`28`us/`54`us/`27`us/`74`us 常量、`19`ms、返回 0=成功注释、无 `delay_uus`、无 printf/GPIO_Init/RCC_、超时计数）
- [x] test_pins.py STM32_MACRO_VALUES 补 2 宏；test_default_layout.py 白名单 PB3 +1（三叠：KEY+GRAY_D6+DHT11）
- [x] UV4 矩阵（init+read(&t,&h)+read_temperature+read_humidity，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核（dht11 已在 wordlist lib_modules——mspm0 条目同 slug 已挂接）；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = 单总线位时序件（DATA_OUT = gpio_init OUT_PP、DATA_IN = gpio_init IU + gpio_get——方向运行时重配；delay_us 忙等不占 TIMER；页面原式 PP+IPU 上拉输入）；默认 PB3（叠 key.KEY_START + pid.GRAY_D6——环境件与独立按键/巡线不同框；页面默认 PB0=MOTOR_B_DIR 不照抄）；时间轴常量单源 dht11_stm32.h（DHT11_START_MS 19/RELEASE_US 20/CHECK_TIME_US 28/WAIT_US 80/BIT0_LOW 54/BIT0_HIGH 27/BIT1_HIGH 74——测试 regex 钉死）；页面缺陷修正 6 条（超时返回 1、返回语义归一 0=成功/1=失败、delay_uus→delay_us、RCU_DHT11 不落、extern 全局收敛 static+出参+便捷封装、5000 空转步→1us 步进 80 步）；采样节拍 ≥2s 归调用方（notes）。UV4 矩阵 0 error/0 module warning（2026-09-06）→ verified=true；mspm0 条目零改动；提交 6418e4c4（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
