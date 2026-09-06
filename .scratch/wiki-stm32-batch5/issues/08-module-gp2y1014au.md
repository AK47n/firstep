# 08 — gp2y1014au 粉尘传感器（ADC 薄封装 + LED 脉冲时序，手册 sensor--gp2y1014au-dust-sensor.md）

**要做什么：** 模块库 `gp2y1014au` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼粉尘驱动为纯驱动切片（ADC 薄封装 + **1×gpio_out LED 脉冲驱动**——页面驱动自带 LED 脉冲但无 LED 脚传感器不工作，mspm0 批 9 修正沿用），API 与 mspm0 版完全对齐：`gp2y1014_init()` + `gp2y1014_read_dust()`（float 估算值——**10ms LED 脉冲周期**：clear→280us→采样→40us→set→9680us（时序常量宏族 `GP2Y1014_LED_SETTLE_US 280u/_LED_SAMPLE_TAIL_US 40u/_LED_CYCLE_TAIL_US 9680u`）+ 0.17×value−0.1 系数 + 5 次快平均（`GP2Y1014_ADC_SAMPLES 5u`；mspm0 另有 FILTER_WINDOW——**实现口径照 mspm0 .c 逐行**））。

**关键事实（%TEMP%\batch5-facts.md）：** F1；页面 OUT=PA5/LED=PA2（推挽低有效）/无 DO；**SAMPLES 30×2ms≈62ms 与 10ms LED 周期矛盾（主缺陷）→ 5 次快平均**；0.17 系数对 ADC 码量纲脱节（页面/mspm0 原式保留，notes——估算值非绝对）；**LED 默认脚 PA2 = DEBUG_UART TX 常备件（不能照抄）→ 默认 PB5**；Filter 全局符号泄漏收敛 static。

**引脚：** pins `GP2Y1014_AO`（adc，PA5，macros `[GP2Y1014_AO_CH]`）+ `GP2Y1014_LED`（gpio_out，**PB5**，macros `[GP2Y1014_LED_GPIO, GP2Y1014_LED_PIN]`）；pin_config.h：`#define GP2Y1014_AO_CH ADC_Channel_5` + `#define GP2Y1014_LED_GPIO GPIO_B` / `#define GP2Y1014_LED_PIN Pin_5`（注释：LED 默认 PB5 叠 hx711 SCK + MOTOR_A_ENC（粉尘与称重/光电编码器闭环不同框）；AO 同 mq2 注释；同选经绑定消解）。

**被谁阻塞：** 无——可立即开始（本批最重件——LED 时序 + 双角色 pins）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/gp2y1014au/code/gp2y1014au_stm32.c/.h`：read_dust 按 mspm0 .c 逐行对齐（LED 脉冲序列 + 采样窗 + 5 次快平均/FILTER 口径 + 0.17 系数）；零引脚字面量/零标准库
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc","delay"]（照 mspm0 现状）、verified false、hardware_bound false、**pins 2 行**（AO+LED）、kit/source_url（wiki 原页 `.../sensor/gp2y1014au-dust-sensor.html`）、notes（手册路径+原页+网盘+**SAMPLES/10ms 周期矛盾修正（5 次快平均）**+LED 必需性+LED 原脚 PA2 弃用→PB5（DEBUG 常备）+0.17 系数量纲脱节（估算值）+Filter 收敛+ADC 共享组+未上板）
- [x] pin_config.h 增 3 宏（AO_CH + LED 2）
- [x] 测试 `tests/test_module_gp2y1014au.py`：形状（2 pins）+宏存在（`GP2Y1014_AO_CH`/`GP2Y1014_LED_GPIO\s+GPIO_B`/`_LED_PIN\s+Pin_5`）+单选生成+守卫（`280u`/`40u`/`9680u` 时序宏、`0.17f`、`GP2Y1014_ADC_SAMPLES 5u`（无 30）、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 3 宏；test_default_layout.py 白名单 PA5 共享组 +1 + PB5 +1（LED——叠 hx711 SCK/MOTOR_A_ENC）
- [x] UV4 矩阵（init+read_dust，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = ADC 薄封装 + **LED 驱动 GPIO 输出（器件必需例外——本批最重件）**：页面 ADC 序列收敛 ml_adc（gp2y1014_init = gpio_init(OUT_PP) + LED 空闲关 + adc_init(ADC_1, GP2Y1014_AO_CH)）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，**ADC 共享组**：与 flame/本批 8 件共读，同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）+ **LED 默认 PB5**（页面原脚 PA2=DEBUG_UART TX 常备件不照抄——叠 hx711 SCK + MOTOR_A_ENC 不同框、同选概率最低，白名单 PB5 +1；GP2Y1014_LED_GPIO/PIN 双宏）；API 与 mspm0 全对齐（gp2y1014_init + gp2y1014_read_dust，float——页面 LED 脉冲序列与 mspm0 .c 逐行对齐：280us/40us/9680us 时序宏族 + 5 次快平均 + 10 点滑动平均内嵌 static（Filter 全局符号收敛）+ 0.17×value−0.1）；**页面 SAMPLES 30×2ms≈62ms 与 10ms LED 周期矛盾（主缺陷）→ 5 次快平均**；0.17 系数量纲脱节（0.17×4095−0.1≈696 超 mg/m³ 量程——相对估算非精标，需标准粉尘标定）；依赖 ["adc","delay"]；页面 stdio 残余剔除；无 DO（4 线：VCC/GND/LED/AOUT）；页面无资料下载链接（仅移植成功案例——notes）；verified=true（UV4 矩阵 0 error/0 module warning，2026-09-06）+ kit/source_url（地阔星 wiki 原页）+ notes（手册路径/矛盾修正/时序/LED 必需性/系数量纲脱节/共享组/未上板）；测试扩展（2 pins 形状/宏存在/单选生成（依赖 adc+delay 展开）/mspm0 零改动/时序+系数守卫）；wordlist 零补录；mspm0 条目零改动；提交 8561ce65（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
