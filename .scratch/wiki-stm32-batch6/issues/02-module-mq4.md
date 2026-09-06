# 02 — mq4 甲烷/天然气检测传感器（ADC 薄封装，手册 sensor--mq-4-sensor.md）

**要做什么：** 模块库 `mq4` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼甲烷/天然气检测驱动为纯驱动切片（ADC 薄封装——页面 ADC 序列收敛 ml_adc），API 与 mspm0 版完全对齐：`mq4_init()` + `mq4_read_percent()`（float 0-100% 相对浓度——正向 `value/4095×100`）。

**关键事实（批 11 spec + batch5 同构断言）：** F1；页面 AO=PA5/DO=PA1（未用——**不声明**）；30×5ms → 5 次快平均；检测对象：甲烷/天然气（对甲烷灵敏度高、对丙烷/丁烷较好、抗酒精等干扰）。

**引脚：** pins `MQ4_AO`（adc，PA5，macros `[MQ4_AO_CH]`）；pin_config.h：`#define MQ4_AO_CH ADC_Channel_5`。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/mq4/code/mq4_stm32.c/.h`（同 mq3 模式）
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc"]、verified false、hardware_bound false、pins 1 行、kit/source_url（`.../sensor/mq-4-sensor.html`）、notes（手册+网盘+5 快平均+DO 不声明+共享组+检测对象+未上板）
- [x] pin_config.h 增 `MQ4_AO_CH`
- [x] 测试 `tests/test_module_mq4.py`（扩展既有文件；守卫同 mq3）
- [x] test_pins.py 补 MQ4_AO_CH；test_default_layout.py 白名单 PA5 组 +1
- [x] UV4 矩阵 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组：并入 batch5 PA5 共读组——16 ADC 角色同脚；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MQ4_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq4_init + mq4_read_percent——甲烷/天然气正向 value/4095×100）；**页面 DO 注释「酒精值」MQ-3 模板串台**——notes 记录不落码（源码零字面量守卫）；SAMPLES 30→5 快平均 + C99 改 uint8_t；DO 未用不声明；verified=true（UV4 0/0，2026-09-06）+ kit/source_url + notes；wordlist 零补录；mspm0 零改动；提交 17b3f4ee（中文）。**

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
