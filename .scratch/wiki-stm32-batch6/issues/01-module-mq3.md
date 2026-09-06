# 01 — mq3 酒精检测传感器（ADC 薄封装，手册 sensor--mq-3-sensor.md）

**要做什么：** 模块库 `mq3` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼酒精/汽油蒸汽检测驱动为纯驱动切片（ADC 薄封装——页面 ADC 序列收敛 ml_adc：`adc_init(ADC_1, MQ3_AO_CH)` + 5 次 `adc_get` 快平均），API 与 mspm0 版完全对齐：`mq3_init()` + `mq3_read_percent()`（float 0-100% 相对浓度——正向 `value/4095×100`，`MQ3_ADC_MAX 4095u` + `MQ3_ADC_SAMPLES 5u`）。

**关键事实（mspm0 批 11 spec + batch5 同构断言）：** F1；页面 AO=PA5/DO=PA1（未用——**不声明**）；页面 30×5ms → 5 次快平均；检测对象：酒精/汽油蒸汽（对酒精灵敏度高、抗汽油/烟雾/水蒸气干扰）；页面 Get_MQ3_DO_value 走 LM393 阈值未用于演示——不声明（notes）。

**引脚：** pins `MQ3_AO`（adc，PA5，macros `[MQ3_AO_CH]`）；pin_config.h：`#define MQ3_AO_CH ADC_Channel_5`（注释同 mq2——ADC 共享组/物理约束：本批 7 件并入 batch5 的 PA5 共读组）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/mq3/code/mq3_stm32.c/.h`（独立 stm32 头；.c 调 `adc_init`/`adc_get`——零寄存器/标准库）
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc"]、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/mq-3-sensor.html`）、notes（手册路径+原页+网盘+5 次快平均+DO 不声明+ADC 共享组+检测对象+未上板）
- [x] pin_config.h 增 `MQ3_AO_CH`
- [x] 测试 `tests/test_module_mq3.py`（照 batch5 模板扩展既有 mspm0 文件）：形状+宏存在+单选生成+mspm0 零改动守卫+守卫（`* 100.0f`/`4095u`、`MQ3_ADC_SAMPLES 5u`、无 printf/GPIO_Init/RCC_、pins 无 DO）
- [x] test_pins.py 补 MQ3_AO_CH；test_default_layout.py 白名单 PA5 组 +1
- [x] UV4 矩阵（init+read_percent，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc：mq3_init = adc_init(ADC_1, MQ3_AO_CH) + 5 次 adc_get 快平均——零寄存器/标准库调用）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，**ADC 共享组**：本批 7 件并入 batch5 的 PA5 共读组（flame + 8 + 7 = 16 ADC 角色同脚），ml_adc 顺序调用无扰；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MQ3_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq3_init + mq3_read_percent，float 0-100% 正向 value/4095×100——酒精/汽油蒸汽，相对值非 ppm 精标，需预热）；页面 SAMPLES 30×5ms→5 次快平均 + C99 for 改 uint8_t；DO 未用不声明（PA1 IPU 演示未用）；verified=true（UV4 矩阵 0 error/0 module warning，2026-09-06）+ kit/source_url（地阔星 wiki 原页）+ notes（手册/网盘/检测对象/共享组/未上板）；测试扩展（形状/宏/单选生成/mspm0 零改动/守卫）；wordlist 零补录；mspm0 条目零改动；提交 6b3a4f43（中文）。**

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
