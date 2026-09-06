# 批次 6「MQ 系收尾」— 立创 wiki 地阔星 STM32F103C8T6 手册模块批量入库（stm32 线）

## 问题陈述

stm32 线进度：批次 1-4 已入库 22 件（GPIO/软 I2C/器件库/气压单总线），批次 5 已入库 8 件 ADC 薄封装（30 件总）。本批 = **MQ 系同构快补收尾**：mq3/mq4/mq6/mq7/mq8/mq9/ms1100 七件——全部「AO 模拟量 + 百分比换算」同构（mspm0 批 11 对应件已入库，stm32 缺条目 = 生成时 missing 警告）。

## 方案

照批次 5 管线（同构快补）。每件：页面「代码块」提炼 → 纯驱动切片（**API 与 mspm0 全对齐**：`<slug>_init()` + `<slug>_read_percent()`（float））→ **页面 ADC 序列代码整体收敛 ml_adc**（`adc_init(ADC_1, <SLUG>_AO_CH)` + 5 次 `adc_get` 快平均）→ pin_config.h 宏（`<SLUG>_AO_CH` = ADC_Channel_5）→ manifest（dependencies ["adc"]、pins 1 行 adc PA5、kit/source_url、notes）→ 测试（照 batch5 模板）→ UV4 矩阵 0/0 → verified=true → 中文提交。

## 用户故事

1. 做题用户选 stm32 + mq3/mq4/mq6/mq7/mq8/mq9/ms1100：`init()` + `read_percent()` 直接出 0-100% 相对浓度（页面原式 + 正文取证），不再「需自备」。
2. 做题用户做酒驾呼气/燃气泄漏/CO 报警/氢气检测/VOC 甲醛监测：不用读器件手册、不用自写 ADC 读取。
3. 维护者：每件 stm32 条目可溯源（dxk wiki 原页 source_url + notes 手册路径/网盘/修正记录/共享组约束）。

## 实现决策

### 既定事实（mspm0 批 11 spec + batch5-facts 同构断言；勿重新调研）

① 七件页面全 F1 标准库、页面 AO 原脚全 **PA5**（dkx 页——与 batch5 八件同构）；DO 脚 = PA1（仅宏/函数未用于演示——**不声明**，LM393 阈值可调电阻，mspm0 先例）；页面采样 30 次 × delay_ms(5)（ms1100 为 30×3ms）→ **5 次快平均**；公式全 **正向 value/4095×100**（页面原式 + 正文取证，与 mq2 定稿方向一致；无 rain 式矛盾）。

② **ms1100 特殊**：页面无百分比函数——read_percent 由页面 demo 电压式 `voltage=(value/4095)×3.3`（Vref 3.3V）推导归一 → `percent = voltage/3.3×100 = value/4095×100`（notes 记录推导）；页面 `Get_DO_Num`/`MS1100_DO`（4K 可调电阻比较）未用于演示不声明；预热 **3-5 分钟**（页面原文）。

③ 默认 AO 全 = **ADC_Channel_5（PA5——页面原脚即共读点）**；pin_config.h 每件 +1 宏（`<SLUG>_AO_CH`，本批 7 宏）；**ADC 共享组**：本批 7 件并入 batch5 的 PA5 共读组（flame + 8 + 7 = 16 ADC 角色同脚——ml_adc 顺序调用无扰；同一物理脚只能接一件器件，多件同测需外部分路器/分时切换——mspm0 MEM0 共读同口径；stm32 通道 10/10 全被既有角色占用——同选经引脚绑定消解）。

④ **API 与 mspm0 全对齐**：`mq3_init()/mq3_read_percent()` … `mq9_init()/mq9_read_percent()`（float 0-100% 正向）+ `ms1100_init()/ms1100_read_percent()`（float 0-100% 正向——推导口径）；宏族 `<SLUG>_ADC_MAX 4095u` + `<SLUG>_ADC_SAMPLES 5u`。

⑤ 依赖 ["adc"]（照 mspm0 现状；stm32 侧 adc 模块 files=[] 内嵌母版 ml_adc）；wordlist 已挂接零补录（7 slug mspm0 批 11 已入库）。

### 各件决策（默认 AO 全 = ADC_Channel_5/PA5，页面原脚即采用；DO 全不声明）

| 工单 | slug | 页面 | 检测对象/notes 要点 |
|---|---|---|---|
| 01 | mq3 | sensor--mq-3-sensor.html | 酒精/汽油蒸汽（对酒精灵敏度高、抗汽油/烟雾/水蒸气干扰）；页面 Get_MQ3_DO_value 未用不声明 |
| 02 | mq4 | sensor--mq-4-sensor.html | 甲烷/天然气（对甲烷灵敏度高、对丙烷/丁烷较好、抗酒精干扰）；DO 未用不声明 |
| 03 | mq6 | sensor--mq-6-sensor.html | 液化气/丙烷（对丁烷/丙烷/甲烷灵敏度高，特别适合液化气）；DO 未用不声明 |
| 04 | mq7 | sensor--mq-7-sensor.html | 一氧化碳（高低温循环检测：低温 1.5V 测 CO、高温 5.0V 清洗——但 4Pin 模块 AO 单路输出；DO 未用不声明） |
| 05 | mq8 | sensor--mq-8-sensor.html | 氢气（对氢气灵敏度高、可检测氢能源相关泄漏）；DO 未用不声明 |
| 06 | mq9 | sensor--mq-9-sensor.html | CO/可燃气体（**器件双温循环原理**：低温 1.5V 测 CO、高温 5.0V 测可燃气并清洗——但页面驱动仅单 AO 单路百分比、4Pin 模块无加热控制脚，双通道区分需模块级温控/标定，本件只读 AO 相对百分比；与 mq7/mq6 分工；DO 未用不声明） |
| 07 | ms1100 | sensor--ms1100-gas-sensor.html | VOC 气体（甲醛/甲苯/苯系，半导体型；工作 5V、<50uA；AOUT 模拟量、DOUT 4K 可调电阻比较；**预热 3-5 分钟**；清洁空气 <1V；页面无百分比函数——demo 电压式推导；与库内 sgp30/ags10（数字量 ppb/ppm VOC）分工：本件廉价模拟相对值；DOUT 未用不声明） |

### 默认脚与重叠全景（定稿）

| slug | 默认脚 | 重叠主体 |
|---|---|---|
| mq3/mq4/mq6/mq7/mq8/mq9/ms1100 | AO=PA5 | **ADC 共享组**：与 flame + batch5 八件共读 PA5（白名单 PA5 组 16 ADC 角色）；现实约束 = 同一物理脚只能接一件器件，多件同测需外部分路器/分时切换（notes，mspm0 MEM0 共读同口径） |

- 白名单：PA5 组 +7（mq3/mq4/mq6/mq7/mq8/mq9/ms1100 AO 角色——**16 ADC 角色共读组**）。

## 测试决策

- 新增 7 个 `tests/test_module_<slug>.py`（照 batch5 test_module_mq2.py 扩展模板——**扩展既有 mspm0 版测试文件**）：manifest 形状（双平台、stm32 pins 元组/宏/依赖 ["adc"]/kit/source_url/notes 子串）+ 母版宏存在断言 + stm32 单选生成全流程 + mspm0 零改动守卫 + 缺陷守卫：
  - 通用：`<SLUG>_AO_CH` 宏（ADC_Channel_5）、`* 100.0f`/`4095u`、`<SLUG>_ADC_SAMPLES 5u`、无 printf/GPIO_Init/RCC_/delay_1ms/stdio、pins 无 DO；
  - ms1100：notes 含「推导」/「3-5 分钟」/「VOC」；源码无页面「电压式」字面量残留（收敛为百分比式）；
  - 各件 notes 含检测对象词（酒精/甲烷/液化气/一氧化碳/氢气/可燃气体/VOC）+ 共享组物理约束 + 未上板。
- `tests/test_pins.py` STM32_MACRO_VALUES 补 7 宏；`tests/test_default_layout.py` 白名单 PA5 组 +7。
- UV4 矩阵（每件，照 batch5 配方；MAIN_C 调 init + read_percent，(void) 化）→ 0 error/0 module warning → verified=true。
- wordlist 零补录（复核即可）。

## 范围外

- mspm0 条目改动（零改动）；上板真机验证（notes）；ppm 精标（相对值）；MQ-9 双温循环加热控制/双通道标定（4Pin 无加热控制脚——notes）；ms1100 页面「电压-甲醛甲苯对应关系」图片换算表（无图注未落码——真机标定留用户）；多路气体多路同测（外部分路器不落码——notes）。

## 补充说明

- 排序：01 mq3 → 02 mq4 → 03 mq6 → 04 mq7 → 05 mq8 → 06 mq9 → 07 ms1100（mq3-09 六件与 batch5 同构照抄 → ms1100 为页面无百分比函数推导件——按简→繁）。
- code-review 裁决（照 mspm0 批 11）：**同构批量豁免逐件深审——随机抽 2 件深审 + 其余 5 件结构对仗核对**，收尾时执行。
- 收尾清单：全量测试 → sweep_7_modules.py 更新 → code-review 两轴 → CONTEXT 补录 → 中文提交。
