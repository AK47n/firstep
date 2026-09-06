# 05 — rain 雨滴传感器（ADC 薄封装 + 方向修正，手册 sensor--rain-sensor.md）

**要做什么：** 模块库 `rain` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼雨滴驱动为纯驱动切片（ADC 薄封装），API 与 mspm0 版完全对齐：`rain_init()` + `rain_read_percent()`（float 0-100% 雨量——**正向 `value/4095×100`：雨越大数字值越大（正文 L50 取证——页面代码 `(1−value/4095)×100` 反向，按正文修正，mspm0 批 9 同款）**，`RAIN_ADC_MAX 4095u` + `RAIN_ADC_SAMPLES 5u`）。

**关键事实（%TEMP%\batch5-facts.md）：** F1；页面 AO=PA5/DO=PA6（唯一——未用不声明）；页面 **3×100ms/20ms 节拍**（5 次快平均修正——页面 30 次级）；GPIOC/GPIOE 串台（L97/102—notes）；delay_1ms 依赖（→delay_ms）；C99 for 声明（按 C89 改写）。

**引脚：** pins `RAIN_AO`（adc，PA5，macros `[RAIN_AO_CH]`）；pin_config.h：`#define RAIN_AO_CH ADC_Channel_5`（注释同 mq2）。

**本件差异化守卫：** 反向映射防回潮——`1.0f - ` 不得出现在 percent 公式（与 photoresistance 的必须出现对仗）。

**被谁阻塞：** 无——可立即开始（本批方向修正核心件）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/rain/code/rain_stm32.c/.h`
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc","delay"]、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/rain-sensor.html`）、notes（手册路径+原页+网盘+**方向修正：正文「雨越大数字值越大」vs 页面反向式——按正文改正向（mspm0 批 9 同款修正）**+GPIOC/GPIOE 串台+delay_1ms 换算+5 次快平均+DO 不声明+ADC 共享组+未上板）
- [x] pin_config.h 增 `RAIN_AO_CH`
- [x] 测试 `tests/test_module_rain.py`：形状+宏存在+单选生成+守卫（**`1.0f - ` 不得出现**+`value / 4095` 正向式守卫+`RAIN_ADC_SAMPLES 5u`+无 printf/GPIO_Init/RCC_/delay_1ms）
- [x] test_pins.py 补宏；test_default_layout.py 白名单 PA5 共享组 +1
- [x] UV4 矩阵 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc：rain_init = adc_init(ADC_1, RAIN_AO_CH) + 5 次 adc_get 快平均）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，**ADC 共享组**：与 flame/本批 8 件共读，同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；RAIN_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（rain_init + rain_read_percent，float 0-100% **正向 value/4095×100——方向修正核心**：页面原式 (1−value/4095)×100 与正文「雨水越大→数字值越大」矛盾 → 按正文取证改正向（mspm0 批 9 同款；守卫「1.0f - 不得出现」× photoresistance 对仗）；页面 3×100ms + get_adc_value 内 delay_ms(20) 节拍→5 次快平均 + delay_1ms 换算并省略（快平均语义）；GPIOC/GPIOE 串台 notes 记录不落码；C99 for 改 uint8_t；DO 未用不声明（PA6 IPU 演示未用且 .h 未声明）；verified=true（UV4 矩阵 0 error/0 module warning，2026-09-06）+ kit/source_url（地阔星 wiki 原页）+ notes（手册路径/网盘/方向修正确据/串台记录/共享组/未上板）；测试扩展（形状/宏/单选生成/mspm0 零改动/**正向防回潮守卫**）；wordlist 零补录；mspm0 条目零改动；提交 ab1c922f（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0；正向守卫绿。
