# 01 — mq2 烟雾检测传感器（ADC 薄封装，手册 sensor--mq-2-sensor.md）

**要做什么：** 模块库 `mq2` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼烟雾检测驱动为纯驱动切片（ADC 薄封装——**页面 ADC 序列代码收敛为 ml_adc**：`adc_init(ADC_1, MQ2_AO_CH)` + 5 次 `adc_get` 快平均），API 与 mspm0 版完全对齐：`mq2_init()` + `mq2_read_percent()`（float 0-100% 相对浓度——正向 `value/4095×100`，`MQ2_ADC_MAX 4095u` + `MQ2_ADC_SAMPLES 5u`）。

**关键事实（%TEMP%\batch5-facts.md）：** F1；页面 AO=PA5（ADC1_CH5）/DO=PA1（仅宏未用——**不声明**，notes）；页面 30 次无延时累加 → 5 次快平均（mspm0 批 9 修正沿用）；**页面 L50「PA27」地猛星串台 + L219 原型重复声明**（notes 不落）；relative %（ppm 精标不承诺）。

**引脚：** pins `MQ2_AO`（type `adc`，default **PA5**，macros `[MQ2_AO_CH]`）；pin_config.h：`#define MQ2_AO_CH ADC_Channel_5`（注释：AO 默认 PA5 = 页面原脚 + 与 flame/同批 8 件共读（**ADC 共享组：同一物理脚只能接一件，多件同测需外部分路器**——mspm0 MEM0 共读同口径）；PA5 现为 flame 通道（独立语义保留为默认不同），共读合法（ml_adc 顺序调用无扰）；同选经绑定换脚（stm32 通道资源 10/10 占满——notes 现实约束））。

**被谁阻塞：** 无——可立即开始（本批打样件）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/mq2/code/mq2_stm32.c/.h`（独立 stm32 头；.c 调 `adc_init`/`adc_get`——零寄存器级/标准库/零引脚字面量（ADC_Channel_N 经宏豁免——照 flame 先例登记豁免理由））
- [x] manifest.json platforms 增 stm32：files `[code/mq2_stm32.c, code/mq2_stm32.h]`、dependencies `["adc","delay"]`（照 mspm0 现状）、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/mq-2-sensor.html`）、notes（手册路径+原页+网盘+「PA27」串台/原型重复记录+5 次快平均+DO 不声明+**ADC 共享组物理约束**（同一脚只能接一件/外部分路）+未上板）
- [x] pin_config.h 增 `MQ2_AO_CH`
- [x] 测试 `tests/test_module_mq2.py`（照 test_module_flame.py）：形状+宏存在（`#define MQ2_AO_CH\s+ADC_Channel_5`）+单选生成全流程+mspm0 零改动守卫+守卫（`* 100.0f`/`4095u`、`MQ2_ADC_SAMPLES 5u`、无 printf/GPIO_Init/RCC_、pins 无 DO）
- [x] test_pins.py STM32_MACRO_VALUES 补 MQ2_AO_CH；test_default_layout.py 白名单 PA5 共享组 +1
- [x] UV4 矩阵（init+read_percent，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列代码收敛 ml_adc：adc_init(ADC_1, MQ2_AO_CH) + 5 次 adc_get 快平均——零寄存器/标准库调用，采样时间 239.5cyc vs 页面 55.5cyc 功能等价差异记录）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，**ADC 共享组**：8 件与 flame 共读 PA5，ml_adc 顺序调用无扰；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；test_default_layout 白名单 PA5 组登记）；MQ2_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq2_init + mq2_read_percent，float 0-100% 正向 value/4095×100）；页面 L50「PA27」地猛星串台 + L219 原型重复——notes 记录不落码（源码零字面量守卫）；SAMPLES 30 次无延时→5 次快平均；DO 未用不声明（PA1 仅宏无初始化）；manifest stm32 条目 verified=true（UV4 矩阵 0 error/0 module warning，2026-09-06）+ kit/source_url（地阔星 wiki 原页）+ notes（手册路径/原页/网盘/串台记录/共享组物理约束/预热相对值/未上板）；测试 test_module_mq2.py 扩展（形状/宏存在/stm32 单选生成/mspm0 零改动守卫/缺陷守卫）；test_pins.py 补 MQ2_AO_CH + test_default_layout.py 白名单 PA5 组；wordlist 零补录复核（slug 已挂接）；mspm0 条目零改动；提交 dc15b804（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
