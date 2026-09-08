# 07 — ms1100 VOC 气体检测传感器（ADC 薄封装 + 公式推导，手册 sensor--ms1100-gas-sensor.md）

**要做什么：** 模块库 `ms1100` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼 VOC 气体检测驱动为纯驱动切片（ADC 薄封装——页面 ADC 序列收敛 ml_adc），API 与 mspm0 版完全对齐：`ms1100_init()` + `ms1100_read_percent()`（float 0-100% 相对浓度——**页面无百分比函数，由页面 demo 电压式 `value/4095×3.3` 推导归一**（Vref 3.3V）→ `percent = voltage/3.3×100 = value/4095×100`——notes 记录推导）。

**关键事实（批 11 spec + batch5 同构断言）：** F1；页面 AO=PA5/页面 4Pin：VCC/GND/DOUT/AOUT（DOUT 数字量，AOUT 与 4K 可调电阻比较——`Get_DO_Num`/`MS1100_DO` 未用于演示——**不声明**）；页面 30×3ms → 5 次快平均；检测对象：甲醛/甲苯/苯等 VOC（半导体型，工作 5V、<50uA、可侦测 0.1ppm 以上）；**预热 3-5 分钟**（页面原文）；清洁空气 <1V；读数相对值（页面未给 ppm 换算表——「采集到的电压与甲醛甲苯的对应关系」为图片无图注、未落码，真机标定留用户）；与库内 sgp30/ags10（数字量 ppb/ppm VOC）分工：本件廉价模拟相对值、两者数字绝对量。

**引脚：** pins `MS1100_AO`（adc，PA5，macros `[MS1100_AO_CH]`）；pin_config.h：`#define MS1100_AO_CH ADC_Channel_5`。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/ms1100/code/ms1100_stm32.c/.h`（同 mq3 模式；read_percent 公式注释含推导）
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc"]、verified false、hardware_bound false、pins 1 行、kit/source_url（`.../sensor/ms1100-gas-sensor.html`）、notes（手册+网盘+5 快平均+DO 不声明+共享组+**推导记录+预热 3-5 分钟+VOC 分工**+未上板）
- [x] pin_config.h 增 `MS1100_AO_CH`
- [x] 测试 `tests/test_module_ms1100.py`（扩展既有文件；守卫同 mq3 + notes 含「推导」/「3-5 分钟」/「VOC」）
- [x] test_pins.py 补 MS1100_AO_CH；test_default_layout.py 白名单 PA5 组 +1
- [x] UV4 矩阵（init+read_percent，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组并入 batch5 PA5 共读组——16 ADC 角色同脚；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MS1100_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（ms1100_init + ms1100_read_percent——**页面无百分比函数，由 demo 电压式 value/4095×3.3 推导归一 read_percent（Vref 3.3V——notes 记录推导）**，VOC/甲醛/苯系正向 value/4095×100；预热 3-5 分钟）；DOUT 未用不声明（4K 可调电阻比较）；与 sgp30/ags10 数字量 VOC 分工 notes；SAMPLES 30×3ms→5 快平均；verified=true（UV4 0/0，2026-09-06）+ kit/source_url + notes；wordlist 零补录；mspm0 零改动；提交 2f6d1b21（中文）。**

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
