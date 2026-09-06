# 04 — photoresistance 光敏电阻（ADC 薄封装，手册 sensor--photoresistance-sensor.md）

**要做什么：** 模块库 `photoresistance` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼光敏驱动为纯驱动切片（ADC 薄封装），API 与 mspm0 版完全对齐：`photoresistance_init()` + `photoresistance_read_percent()`（float 0-100% 亮度——**反向 `(1−value/4095)×100`：最亮 100 最暗 0，与正文自洽——本批唯二反向自洽页（与 rain 对仗——rain 修正向、本件保留反向），`PHOTORESISTANCE_ADC_MAX 4095u` + `PHOTORESISTANCE_ADC_SAMPLES 5u`）。

**关键事实（%TEMP%\batch5-facts.md）：** F1；页面 AO=PA5/DO=PA2（未用——不声明）；页面 10 次采样 → 5 次快平均；main 演示重复 10 次采样（不落）；stdio 残余 include（剔除）。

**引脚：** pins `PHOTORESISTANCE_AO`（adc，PA5，macros `[PHOTORESISTANCE_AO_CH]`）；pin_config.h：`#define PHOTORESISTANCE_AO_CH ADC_Channel_5`（注释同 mq2）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/photoresistance/code/photoresistance_stm32.c/.h`
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc","delay"]、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/photoresistance-sensor.html`）、notes（手册路径+原页+网盘+**反向式保留（正文自洽）——勿照 rain 修正**+5 次快平均+DO 不声明+ADC 共享组+未上板）
- [x] pin_config.h 增 `PHOTORESISTANCE_AO_CH`
- [x] 测试 `tests/test_module_photoresistance.py`：形状+宏存在+单选生成+守卫（**`1.0f - ` 必须出现**（反向保留守卫——与 rain 的「不得出现」对仗）+`4095u`+`PHOTORESISTANCE_ADC_SAMPLES 5u`+无 printf/GPIO_Init/RCC_/stdio）
- [x] test_pins.py 补宏；test_default_layout.py 白名单 PA5 共享组 +1
- [x] UV4 矩阵 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc：photoresistance_init = adc_init(ADC_1, PHOTORESISTANCE_AO_CH) + 5 次 adc_get 快平均）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，**ADC 共享组**：与 flame/本批 8 件共读，同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；PHOTORESISTANCE_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（photoresistance_init + photoresistance_read_percent，float 0-100% **反向 (1−value/4095)×100 自洽保留**——页面「最亮 100 最暗 0」，本批唯一反向自洽页；守卫「1.0f - 必须出现」× rain 对仗勿改反）；页面 Get_Adc_Value(10)→5 次快平均 + stdio 残余 include 剔除；DO 未用不声明（PA2 IPU 演示未用）；verified=true（UV4 矩阵 0 error/0 module warning，2026-09-06）+ kit/source_url（地阔星 wiki 原页）+ notes（手册路径/网盘/反向自洽保留/共享组/未上板）；测试扩展（形状/宏/单选生成/mspm0 零改动/反向守卫）；wordlist 零补录；mspm0 条目零改动；提交 52bd0276（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
