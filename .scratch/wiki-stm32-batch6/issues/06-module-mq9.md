# 06 — mq9 一氧化碳/可燃气体检测传感器（ADC 薄封装，手册 sensor--mq-9-sensor.md）

**要做什么：** 模块库 `mq9` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼 CO/可燃气体检测驱动为纯驱动切片（ADC 薄封装——页面 ADC 序列收敛 ml_adc），API 与 mspm0 版完全对齐：`mq9_init()` + `mq9_read_percent()`（float 0-100% 相对浓度——正向 `value/4095×100`）。

**关键事实（批 11 spec + batch5 同构断言）：** F1；页面 AO=PA5/DO=PA1（未用——**不声明**）；30×5ms → 5 次快平均；**notes 写明器件双温循环原理**（低温 1.5V 测 CO、高温 5.0V 测可燃气体并清洗——但页面驱动仅单 AO 单路百分比、4Pin 模块无加热控制脚，双通道区分需模块级温控/标定，本件只读 AO 相对百分比；与 mq7（CO 专一）/mq6（可燃气专一）分工）。

**引脚：** pins `MQ9_AO`（adc，PA5，macros `[MQ9_AO_CH]`）；pin_config.h：`#define MQ9_AO_CH ADC_Channel_5`。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/mq9/code/mq9_stm32.c/.h`（同 mq3 模式）
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc"]、verified false、hardware_bound false、pins 1 行、kit/source_url（`.../sensor/mq-9-sensor.html`）、notes（手册+网盘+5 快平均+DO 不声明+共享组+**双温循环原理与分工说明**+未上板）
- [x] pin_config.h 增 `MQ9_AO_CH`
- [x] 测试 `tests/test_module_mq9.py`（扩展既有文件；守卫同 mq3 + notes 含「双温循环」）
- [x] test_pins.py 补 MQ9_AO_CH；test_default_layout.py 白名单 PA5 组 +1
- [x] UV4 矩阵 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组并入 batch5 PA5 共读组——16 ADC 角色同脚；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MQ9_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq9_init + mq9_read_percent——CO/可燃气正向 value/4095×100）；**器件双温循环原理说明**（低温 1.5V 测 CO、高温 5.0V 测可燃气并清洗——页面驱动仅单 AO 单路百分比、4Pin 模块无加热控制脚，双通道区分需模块级温控/标定；与 mq7/mq6 分工——notes）；「酒精值」串台 notes；SAMPLES 30→5 快平均 + C99 改 uint8_t；DO 未用不声明；verified=true（UV4 0/0，2026-09-06）+ kit/source_url + notes；wordlist 零补录；mspm0 零改动；提交 09f2d0ef（中文）。**

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
