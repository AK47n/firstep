# 01 — us016 超声波测距（ADC 薄封装，手册 sensor--us-016-ultrasonic-ranging-sensor.md）

**要做什么：** 模块库 `us016` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼超声波测距驱动为纯驱动切片（ADC 薄封装——页面 ADC 序列收敛 ml_adc），API 与 mspm0 版完全对齐：`us016_init()` + `us016_read_distance_cm()`（float 厘米——**与 mspm0 同名（us016.h L30）**；采样 = **`US016_ADC_SAMPLES 5`**（照 mspm0 us016.c，页面 50 次×10ms≈500ms → 5 次快平均）；换算 = **双量程宏 `US016_RANGE_1M`**（照 mspm0 us016.h L19——0 = 3m 量程档系数 **0.75f**、1 = 1m 量程档系数 **0.25f**（=3072/4096；页面正文 L49「3096」与代码/注释「3072」不一致——按代码 0.75 定稿、mspm0 批 2 同款）；默认 **0**（0.75 档）——stm32 沿 mspm0 双档宏设计，页面默认配置档以 mspm0 为准）。

**关键事实（%TEMP%\batch7-facts.md）：** F1；页面默认 AO=PA5（即共读点——**采用**）；出参 cm（页面 main /10）。

**引脚：** pins `US016_AO`（adc，PA5，macros `[US016_AO_CH]`）；pin_config.h：`#define US016_AO_CH ADC_Channel_5`（注释：AO 默认 PA5 与 flame/批 5 件共存（ADC 共享组）；**与 ir_distance 互替件同脚**（互替同脚先例——二选一接入）；物理约束：同一物理脚只能接一件；同选经绑定换 PA0/PA1）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/us016/code/us016_stm32.c/.h`（独立 stm32 头；adc_init/adc_get + 5 次快平均；零引脚字面量）
- [x] manifest.json platforms 增 stm32：files `[code/us016_stm32.c, code/us016_stm32.h]`、dependencies ["adc","delay"]（照 mspm0 现状）、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/us-016-ultrasonic-ranging-sensor.html`）、notes（手册路径+原页+网盘+**3096/3072 系数记录（按代码 0.75）**+500ms→5 次快平均+互替 ir_distance+ADC 共享组约束+未上板）
- [x] pin_config.h 增 `US016_AO_CH`
- [x] 测试 `tests/test_module_us016.py`（照 test_module_mq2.py）：形状+宏存在+单选生成+mspm0 零改动+守卫（`US016_ADC_SAMPLES 5`、`US016_RANGE_1M 0` + `0.25f`/`0.75f` 双档系数、出参 cm 注释、无 0.769/3096 式、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补宏；test_default_layout.py 白名单 PA5 组 +1
- [x] UV4 矩阵 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-07）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组并入 batch5 PA5 共读组——flame+8+7+1 = 17 ADC 角色同脚；与 ir_distance **互替件同脚**——同一物理脚只能接一件，互替同脚先例语义（二选一接入无需另消解）；白名单 PA5 组登记）；US016_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（us016_init + us016_read_distance_cm——与 mspm0 同名 us016.h L30；出参 cm = mm/10，页面 main L254 换算归入 API）；双量程宏 US016_RANGE_1M=0（0=3m 档 0.75f/1=1m 档 0.25f——页面正文 3096 vs 代码 3072 按代码 0.75，mspm0 批 2 同款）+ Vref/Vcc 修正宏（US016_VREF_V/US016_VCC_V 默认 3.3/3.3）；SAMPLES 50×10ms≈500ms→5 快平均（US016_ADC_SAMPLES 5）；Range 量程脚无 GPIO 代码/4Pin 无 DO——均不声明；verified=true（UV4 0 error/0 module warning，2026-09-07）+ kit/source_url + notes（手册路径/原页/网盘/3096-3072 记录/500ms→5 次/互替 ir_distance/ADC 共享组约束/未上板）；wordlist 零补录（us016 已在词表感知传感器 models + lib_modules）；mspm0 零改动；description 双平台化（批 6 遗留「存量 description 措辞统一」顺带整改本件）；test_pins 宏表 +US016_AO_CH、test_default_layout PA5 白名单 +us016.US016_AO。**

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
