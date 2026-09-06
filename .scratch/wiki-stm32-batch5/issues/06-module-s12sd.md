# 06 — s12sd 紫外线传感器（ADC 薄封装 + 档位表，手册 sensor--s12sd-uv-sensor.md）

**要做什么：** 模块库 `s12sd` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼紫外线驱动为纯驱动切片（ADC 薄封装——3Pin 无 DO），API 与 mspm0 版完全对齐：`s12sd_init()` + `s12sd_read_uv_index()`（**uint8 档位 0-11 级**——档位表上界 227/318/408/503/606/696/795/881/976/1079/1170 逐档常量单源，非百分比；`S12SD_ADC_SAMPLES 5u`）。

**关键事实（%TEMP%\batch5-facts.md）：** F1；页面 SIG=PA5（无 DO——3Pin）；页面 30×5ms → 5 次快平均；**L289「IRtracking demo start」串台**（notes）；表头「num采集次数」残留（notes）。

**引脚：** pins `S12SD_AO`（adc，PA5，macros `[S12SD_AO_CH]`）；pin_config.h：`#define S12SD_AO_CH ADC_Channel_5`（注释同 mq2）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/s12sd/code/s12sd_stm32.c/.h`
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc","delay"]、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/s12sd-uv-sensor.html`）、notes（手册路径+原页+网盘+IRtracking 串台+档位表（照 mspm0 逐档）+5 次快平均+ADC 共享组+未上板）
- [x] pin_config.h 增 `S12SD_AO_CH`
- [x] 测试 `tests/test_module_s12sd.py`：形状+宏存在+单选生成+守卫（档位表上界常量 227/318/408/503/606/696/795/881/976/1079/1170、`S12SD_ADC_SAMPLES 5u`、无 printf/GPIO_Init/RCC_、无「IRtracking」源码字面量）
- [x] test_pins.py 补宏；test_default_layout.py 白名单 PA5 共享组 +1
- [x] UV4 矩阵（init+read_uv_index，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc：s12sd_init = adc_init(ADC_1, S12SD_AO_CH) + 5 次 adc_get 快平均）；默认 SIG = ADC_Channel_5（PA5——页面原脚即共读点，**ADC 共享组**：与 flame/本批 8 件共读，同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；S12SD_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（s12sd_init + s12sd_read_uv_index，**uint8 档位表 0-11**：227/318/408/503/606/696/795/881/976/1079/1170 逐档上界——页面阈值表原式，非百分比；页面形参式 Get_Ultraviolet_Intensity(uint16_t) 收敛为模块内自读）；3Pin 无 DO；页面 L289「IRtracking demo start」串台 notes 记录不落码（源码零字面量守卫）+ L133-135 表头形参注释残留不落码；SAMPLES 30×5ms→5 次快平均；verified=true（UV4 矩阵 0 error/0 module warning，2026-09-06）+ kit/source_url（地阔星 wiki 原页）+ notes（手册路径/网盘/档位表/串台记录/共享组/未上板）；测试扩展（形状/宏/单选生成/mspm0 零改动/档位表守卫）；wordlist 零补录；mspm0 条目零改动；提交 22d0f318（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
