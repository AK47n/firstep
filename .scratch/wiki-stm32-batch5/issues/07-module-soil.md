# 07 — soil 土壤湿度传感器（ADC 薄封装，手册 sensor--soil-moisture-sensor.md）

**要做什么：** 模块库 `soil` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼土壤湿度驱动为纯驱动切片（ADC 薄封装），API 与 mspm0 版完全对齐：`soil_init()` + `soil_read_percent()`（float 0-100% 湿度——正向 `value/4095×100`，`SOIL_ADC_MAX 4095u` + `SOIL_ADC_SAMPLES 5u`）。

**关键事实（%TEMP%\batch5-facts.md）：** F1；页面 AO=PA5/DO=PA1（未用——不声明）；页面 30 次 → 5 次快平均；**L138-140 DMA 函数名残留（Get_Adc_Dma_Value）+ L186「可燃气体」串台**（notes）；**stm32 侧无 mspm0 板 PA14 的 15k 固定衰减问题**（mspm0 默认脚 PA14 板载 LED 负载特例——stm32 PA5 无板载负载，notes 澄清；若用户接 PA0/1（板载 LED 分流）再考虑——脚本提示）。

**引脚：** pins `SOIL_AO`（adc，PA5，macros `[SOIL_AO_CH]`）；pin_config.h：`#define SOIL_AO_CH ADC_Channel_5`（注释同 mq2）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/soil/code/soil_stm32.c/.h`
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc","delay"]、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/soil-moisture-sensor.html`）、notes（手册路径+原页+网盘+DMA 残留/「可燃气体」串台+5 次快平均+DO 不声明+**无 15k 衰减问题澄清（mspm0 PA14 特例）**+ADC 共享组+未上板）
- [x] pin_config.h 增 `SOIL_AO_CH`
- [x] 测试 `tests/test_module_soil.py`：形状+宏存在+单选生成+守卫（`* 100.0f`/`4095u`+`SOIL_ADC_SAMPLES 5u`+无 printf/GPIO_Init/RCC_/DMA 字面量）
- [x] test_pins.py 补宏；test_default_layout.py 白名单 PA5 共享组 +1
- [x] UV4 矩阵 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc：soil_init = adc_init(ADC_1, SOIL_AO_CH) + 5 次 adc_get 快平均）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，**ADC 共享组**：与 flame/本批 8 件共读，同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；SOIL_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（soil_init + soil_read_percent，float 0-100% 正向 value/4095×100——相对湿度非绝对值）；**stm32 侧无 mspm0 板 PA14 板载 LED2+15k 固定衰减问题**（mspm0 默认脚物理特性——stm32 默认 PA5 排针 ADC 脚无板载负载，notes 澄清）；页面 L138-140 DMA 函数名残留（Get_Adc_Dma_Value）+ L186「可燃气体」串台——notes 记录不落码（源码零字面量守卫）；SAMPLES 30×5ms→5 次快平均；DO 未用不声明（PA1 IPU 演示未用）；verified=true（UV4 矩阵 0 error/0 module warning，2026-09-06）+ kit/source_url（地阔星 wiki 原页）+ notes（手册路径/网盘/DMA 与串台记录/15k 澄清/共享组/未上板）；测试扩展（形状/宏/单选生成/mspm0 零改动/守卫）；wordlist 零补录；mspm0 条目零改动；提交 0d5a4c0f（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
