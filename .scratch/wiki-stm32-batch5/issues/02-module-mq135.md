# 02 — mq135 空气质量传感器（ADC 薄封装，手册 sensor--mq-135-sensor.md）

**要做什么：** 模块库 `mq135` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼空气质量检测驱动为纯驱动切片（ADC 薄封装），API 与 mspm0 版完全对齐：`mq135_init()` + `mq135_read_percent()`（float 0-100% 相对浓度——正向 `value/4095×100`，`MQ135_ADC_MAX 4095u` + `MQ135_ADC_SAMPLES 5u`）。

**关键事实（%TEMP%\batch5-facts.md）：** F1；页面 AO=PA5/DO=PA1（IPU 已初始化但演示未用——**不声明**）；页面 30×5ms → 5 次快平均；**L185「酒精值」串台**（notes）。

**引脚：** pins `MQ135_AO`（adc，PA5，macros `[MQ135_AO_CH]`）；pin_config.h：`#define MQ135_AO_CH ADC_Channel_5`（注释同 mq2——ADC 共享组/物理约束）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/mq135/code/mq135_stm32.c/.h`（同 mq2 模式）
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc","delay"]、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/mq-135-sensor.html`）、notes（手册路径+原页+网盘+「酒精值」串台+5 次快平均+DO 不声明+ADC 共享组约束+未上板）
- [x] pin_config.h 增 `MQ135_AO_CH`
- [x] 测试 `tests/test_module_mq135.py`（同 mq2 模板：形状/宏存在/单选生成/守卫——`* 100.0f`、`4095u`、`MQ135_ADC_SAMPLES 5u`、无串台字面量「酒精值」（notes 仅记录）、无 DO）
- [x] test_pins.py 补 MQ135_AO_CH；test_default_layout.py 白名单 PA5 共享组 +1
- [x] UV4 矩阵 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc：mq135_init = adc_init(ADC_1, MQ135_AO_CH) + 5 次 adc_get 快平均）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，**ADC 共享组**：与 flame/本批 8 件共读，同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MQ135_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq135_init + mq135_read_percent，float 0-100% 正向 value/4095×100）；页面 L185「酒精值」串台（MQ-3 模板残留）——notes 记录不落码（源码零字面量守卫）；SAMPLES 30×5ms→5 次快平均；C99 for 改 uint8_t；DO 未用不声明（PA1 IPU 演示未用）；verified=true（UV4 矩阵 0 error/0 module warning，2026-09-06）+ kit/source_url（地阔星 wiki 原页）+ notes（手册路径/网盘/串台记录/共享组/未上板）；测试扩展（形状/宏/单选生成/mspm0 零改动/守卫）；wordlist 零补录；mspm0 条目零改动；提交 afacae0f（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
