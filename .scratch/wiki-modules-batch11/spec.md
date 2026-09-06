# 批次 11「MQ 系同构快补收尾」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1-10 共 39 件已入库（遥控/通信、传感器常用、显示/执行、语音/身份、I2C 增强件、环境监测/温度补充第一组、气体/空气传感器第一组、环境类第二组、ADC 模拟量薄封装群、杂项收尾第一组）。`lckfb-地猛星移植手册/` 剩余页中 **MQ 系同构快补收尾**七篇页内自带完整驱动源码（v7 审计自包含，`.scratch/wiki-materials/audit_v7.py` 2026-09-11 复跑确认 12 篇真缺页外符号名单中无本批七件）：MQ-3 酒精/汽油蒸汽、MQ-4 甲烷/天然气、MQ-6 液化气/丙烷、MQ-7 一氧化碳、MQ-8 氢气、MQ-9 一氧化碳/可燃气体、MS1100 VOC 气体——模块库仍无对应条目：用户做酒驾呼气检测/燃气泄漏报警/一氧化碳报警/氢气检测/VOC 甲醛监测题时，AI 不知道库里有驱动，只能当"需自备"。

按用户裁决：批次 11 = **MQ 系同构快补收尾**七件——全部页内源码完整（v7 全自洽）、无需网盘；**沿用 mq2 薄封装模式**（MEM 槽位已满 8/8，mq135/mq5 的独立 MEM 模式不可再复制）。

## 方案

照批次 1-10 已确立管线，每件一个工单：手册「代码块」提炼完整 bsp（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机）→ **ADC 薄封装共读 MEM0**（无新 ADC 通道/实例/无新 `$assign` 行——mq2/us016/批次 9 先例）→ `syscfg_instances.py` INSTANCE_CONSUMERS 按 mq2 登记方式（ADC12_0 消费表加 slug）→ manifest（dependencies/pins 照 mq2/kit+source_url/notes 含手册路径+原页+网盘链接+改造要点+方向取证+MQ 系限制）→ wordlist.json 补录（感知传感器，lib_modules 挂接）→ 测试（`test_module_<slug>.py` 照 test_module_mq2.py 模板；test_pins.py / test_pin_bindings.py / test_syscfg_prune.py 增断言）→ 编译矩阵（复制 run_mq2_matrix.py 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified=true 回写 → 中文提交 → 工单 resolved → code-review（**同构批量豁免逐件深审：随机抽 2 件深审 + 其余 5 件结构同构对仗核对**，本 spec 记录该裁决）。

## 用户故事

1. 作为做题用户，我选中 `mq3`/`mq4`/`mq6`/`mq7`/`mq8`/`mq9`/`ms1100` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + read_percent 读相对浓度百分比。
2. 作为做题用户，我做酒精/燃气泄漏/一氧化碳/氢气/VOC 甲醛检测与报警时，不用再读器件手册、不用自写 ADC 读取时序。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/方向取证/编译记录），可溯源到手册。

## 实现决策

### 既定事实（勿重新调研，批次 1-10 已实证）

① ADC12_0 **八通道已满**（endAdd=7：MEM0=adc/us016/mq2/批次 9 四件薄封装共读 / MEM1-2=joystick X/Y / MEM3=ir_distance / MEM4=mq135 / MEM5=mq5 / MEM6=flame / MEM7=soil）——**本批及以后 ADC 类一律薄封装共读 MEM0**（mq2/us016 先例：多件同选同读一物理通道、一次转换一次读、采样节奏按用途自协调，绑定换引脚 = 改写 adcPin*.$assign + adcMem*chansel，模块零改动；手册原脚 PA27/A0_0 经绑定即可复现——绑 PA27 时改写器按通道号换 adcPin3→adcPin0 + adcMem0chansel→CHAN_0）；② SysConfig 拒绝同一 UART 外设多实例——本批无 UART 件；③ 地猛星 2×20 排针 31 个 IO 全被默认布局占用——本批无新 GPIO 实例（薄封装），无新增默认脚分配；④ PA0/PA1 不可作 GPIO 输入——本批无 GPIO 角色；⑤ 母版 GPIO 中断全走 GROUP1 单向量且被 motor 编码器独占——本批全部经 adc 模块 API 轮询，不注册中断；⑥ 工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`；⑦ 页内符号异常/器件正确性缺漏→人工复核、修正并记 notes（mq 系页面 DO 宏/数字常量若有肉眼可见错字按先例修正）；⑧ 一致性快检先例 `.scratch/wiki-modules-batch10/sweep_39_modules.py` → 本批后更新 46 件版（`sweep_46_modules.py`）。

### 共性（七件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 bsp，改造为 `xxx_init()` + `xxx_read_percent()`，去 main/printf，函数名规范化（去 `ADC_MQx_Init`/`ADC_GET`/`Get_Adc_MQx_Value`/`Get_MQx_Percentage_value` 菜市场命名；ms1100 去 `MS1100_Init`/`Get_ADC_Value`），全局状态收敛为模块内静态（本批无全局态——gCheckADC 标志随页面中断一并去除）。
- **ADC 轮询**：页面 `ADC12_0_INST_IRQHandler` + `gCheckADC` 标志位一律改经 adc 模块 API 轮询（`xxx_init` = `adc_init(ADC_1, ADC_Channel_0)`；`xxx_read_percent` 内 `adc_get(ADC_1, ADC_Channel_0)`——共享实例 IRQHandler 强符号唯一，mq2 先例）。
- **换算与方向**：百分比 = `(float)value/(float)4095*100.0f` **正向映射**（value/4095×100——页面原式；正文字证：MQ 系「电导率随浓度增加而增大」→ AO 电压随浓度升高 → ADC 值升高 → 百分比升高；ms1100「AOUT 为气体量对应电压值、清洁空气 <1V」→ 同向）。**本批七件全部与 mq2 同构、方向定稿与 mq2 一致（正向）**——页面原式与代码一致、无 rain 式正文/公式矛盾（若核对中发现不一致按正文为准并记 notes）；ms1100 页面无百分比函数——read_percent 由页面 demo 电压原式推导：`voltage=(value/4095)×3.3`（Vref 3.3V）→ `percent=voltage/3.3×100=value/4095×100`（notes 记录推导）。
- **采样**：页面 SAMPLES 30 × delay_ms(3/5) 改 **5 次快平均**（MQ2_ADC_SAMPLES=5 命名 `MQx_ADC_SAMPLES`，us016 快平均先例；毫秒级延时去除）。
- **页面 DO（LM393 阈值比较）宏未用不声明**（mq3/4/6/7/8/9 页面 `Get_MQx_DO_value`/`MQ_DO` 宏、ms1100 `Get_DO_Num`/`MS1100_DO`——页面 main 演示均未调 DO 函数——mq2 同策略：阈值由模块可调电阻控制，需要时经引脚绑定 GPIO 输入自读，notes 写明）。
- **默认脚 = PA24**（ADC12_0 MEM0 槽位，无新 `$assign` 行，manifest 按 mq2 声明方式对齐：角色 id `MQx_AO_CH0`/`MS1100_AO_CH0`、type adc、default PA24、required true；`_CH0` 尾命名 = MEM0 索引，us016 先例）。
- **notes 统一口径**（逐件写明，mq2 模板）：① MQ 系读数是**相对值非 ppm 精标**（浓度-电压非线性、上电预热 3-5 分钟/湿度影响、不同型号灵敏度不同，真实 ppm 需标准气体标定）；② **多路气体同选共读 MEM0 物理通道限制**（薄封装模式——每路只能接一个器件到 PA24；多路同选场景需外部分路或换独立通道——MEM 槽位已满 8/8，现实约束）；③ **正向映射取证**（页面原式与正文一致性）；④ 手册原脚 PA27 经绑定复现；⑤ 依赖 adc 模块（共享 ADC12_0 实例，IRQHandler 强符号唯一）。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `mq3` | sensor--mq-3-sensor.md | ADC 模拟量薄封装（AO 输出，电压 → 百分比） | **无新实例**——依赖 adc 模块共享 ADC12_0 MEM0 槽位（mq2/us016 先例） | `dependencies: ["adc"]`；API = `mq3_init` + `mq3_read_percent`（0-100% 相对浓度——页面 Get_MQ3_Percentage_value 原式 value/4095×100 **正向映射**，正文「电导率随酒精蒸气浓度增加而增大」同向；页面 30×5ms 改 5 次快平均）；页面 ADC 中断改轮询；页面 `Get_MQ3_DO_value`/`MQ_DO`（LM393 阈值）未用于演示不声明；检测对象：**酒精/汽油蒸汽**（对酒精灵敏度高、抗汽油/烟雾/水蒸气干扰）；notes 按上表统一口径；默认 PA24（MEM0）；角色 id `MQ3_AO_CH0` |
| `mq4` | sensor--mq-4-sensor.md | 同上（甲烷/天然气） | 无新实例（同上） | 同 mq3 同构照抄（差异仅检测对象/页面函数名/演示串）；API = `mq4_init` + `mq4_read_percent`（value/4095×100 正向——正文「电导率随可燃气体浓度增加而增大」）；页面 30×5ms 改 5 次快平均；页面 `Get_MQ4_DO_value`/`MQ_DO` 不声明；检测对象：**甲烷/天然气**（对甲烷灵敏度高、对丙烷/丁烷较好）；默认 PA24；角色 id `MQ4_AO_CH0` |
| `mq6` | sensor--mq-6-sensor.md | 同上（液化气/丙烷） | 无新实例（同上） | 同构照抄；API = `mq6_init` + `mq6_read_percent`（value/4095×100 正向——正文「对丁烷/丙烷/甲烷灵敏度高」）；页面 30×5ms 改 5 次快平均；页面 `Get_MQ6_DO_value`/`MQ_DO` 不声明；检测对象：**液化气/丙烷**（兼顾甲烷/丁烷）；默认 PA24；角色 id `MQ6_AO_CH0` |
| `mq7` | sensor--mq-7-sensor.md | 同上（一氧化碳） | 无新实例（同上） | 同构照抄；API = `mq7_init` + `mq7_read_percent`（value/4095×100 正向——页面描述「电导率随一氧化碳浓度增加而增大」，高低温循环检测但 4Pin 模块 AO 单路输出）；页面 30×5ms 改 5 次快平均；页面 `Get_MQ7_DO_value`/`MQ_DO` 不声明；检测对象：**一氧化碳**；默认 PA24；角色 id `MQ7_AO_CH0` |
| `mq8` | sensor--mq-8-sensor.md | 同上（氢气） | 无新实例（同上） | 同构照抄；API = `mq8_init` + `mq8_read_percent`（value/4095×100 正向——正文「电导率随氢气浓度增加而增大」）；页面 30×5ms 改 5 次快平均；页面 `Get_MQ8_DO_value`/`MQ_DO` 不声明；检测对象：**氢气**（对氢气灵敏度高）；默认 PA24；角色 id `MQ8_AO_CH0` |
| `mq9` | sensor--mq-9-sensor.md | 同上（CO/可燃气体） | 无新实例（同上） | 同构照抄；API = `mq9_init` + `mq9_read_percent`（value/4095×100 正向）；页面 30×5ms 改 5 次快平均；页面 `Get_MQ9_DO_value`/`MQ_DO` 不声明；**notes 写明器件双温循环原理**（低温 1.5V 测 CO、高温 5.0V 测可燃气体并清洗——但页面驱动仅单 AO 单路百分比、4Pin 模块无加热控制脚，双通道区分需模块级温控/标定，本件只读 AO 相对百分比；与 mq7（CO 专一）/mq6（可燃气专一）分工）；默认 PA24；角色 id `MQ9_AO_CH0` |
| `ms1100` | sensor--ms1100-gas-sensor.md | 同上（VOC/甲醛/苯系） | 无新实例（同上） | `dependencies: ["adc"]`；API = `ms1100_init` + `ms1100_read_percent`（0-100% 相对浓度——**页面无百分比函数，由 demo 电压式推导**：`voltage=(value/4095)×3.3`（页面原式）→ `percent=voltage/3.3×100=value/4095×100`（Vref 3.3V 满量程归一；**正向映射**——正文「AOUT 为气体量对应电压值、清洁空气电压 <1V」）；页面 30×3ms 改 5 次快平均）；页面 ADC 中断改轮询；页面 `Get_DO_Num`/`MS1100_DO`（可调电阻阈值比较）未用于演示不声明；**notes 写明**：对甲醛/甲苯/苯等 VOC 灵敏（半导体型）、工作 5V、**预热 3-5 分钟**（页面原文）、清洁空气 <1V、读数相对值（页面未给 ppm 换算表——「采集到的电压与甲醛甲苯的对应关系」为图片无图注、未落码，真机标定留用户）；与库内 sgp30/ags10（数字量 ppb/ppm VOC）分工：本件廉价模拟相对值、两者数字绝对量；与 MQ 系分工：VOC 专用 vs 可燃气体；默认 PA24；角色 id `MS1100_AO_CH0` |

### 默认脚与重叠全景（2026-09-11 定稿）

七件默认 = **PA24（全七件 ADC 角色，MEM0 槽位无新 `$assign` 行）**——无新 GPIO 实例、无新默认脚分配。

- PA24 计数不变（仍 6：HUIDU L3 + UWB_UART RX + ADC12_0 adcPin3（adc/us016/mq2/批次 9 四件/本批七件薄封装共读——**无新 $assign 行**）+ HC05_UART RX + NRF24L01 CSN + TCS34725 SDA），test_pin_bindings 刻意表 PA24 注释补本批七件。
- 与批次 5 tcs34725 SDA / 无线族重叠系 MEM0 槽位唯一所致（mq2 同口径，同选经引脚绑定消解——tcs34725 SDA 或本批 ADC 件换脚即可）。
- **多路气体同选现实约束**：七件 + mq2 + 批次 9 ADC 四件同选时全部共读同一物理通道 PA24/MEM0——同一引脚只能接一个器件（薄封装模式）；多路气体**同时**测需外部分路（模拟多路开关/分时切换）或换独立通道（**MEM 槽位已满 8/8 现实不可行**，板上无剩余 ADC 通道）——notes 逐件写明。

### 网盘依赖（本批无）

本批七件页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞：全部未上板（ADC 换算方向/预热/湿度影响真机验证留后续）。

## 测试决策

照批次 1-10 先例逐件：

- `tests/test_pins.py`：`test_module_code_has_no_pin_literals` 豁免元组增 `"mq3","mq4","mq6","mq7","mq8","mq9","ms1100"`（ADC_Channel_N 为 API 对偶枚举，docstring 同步）；无 MSPM0_DEFAULT_MAP 新增（adc 角色无 GPIO 组/外设字段落点，mq2/us016 先例）。
- `tests/test_pin_bindings.py` 刻意重叠表：PA24 注释补本批七件薄封装共读（计数不变 6）。
- `tests/test_syscfg_prune.py`：ADC12_0 新消费方断言 7 条（mq3/mq4/mq6/mq7/mq8/mq9/ms1100 单选保留 ADC12_0）。
- 新增 `tests/test_module_mq3.py` / `test_module_mq4.py` / `test_module_mq6.py` / `test_module_mq7.py` / `test_module_mq8.py` / `test_module_mq9.py` / `test_module_ms1100.py`（照 test_module_mq2.py 模板）：manifest 结构（仅 mspm0 + 依赖 adc + 单角色 = adc PA24）+ mspm0 单选生成（syscfg 裁剪保留 ADC12_0、模块文件落盘、依赖 adc 文件落盘、main.c 调 init/read_percent 过静态门禁）+ **公式守卫**（`<SLUG>_ADC_MAX`/`4095u`、`* 100.0f`、`/ (float)<SLUG>_ADC_MAX`、`ADC_Channel_0`）+ **无 IRQHandler 守卫**（`ADC12_0_INST_IRQHandler`/`gCheckADC` 不得出现）+ notes 守卫（「相对值」「ppm」「预热」——ms1100 另含「3-5 分钟」或「5 分钟」「VOC」）。
- 编译级验收：复制 `run_mq2_matrix.py` 改 slug（七件各一，放 .scratch/wiki-modules-batch11/），gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- stm32 平台条目、上板真机验证（真机留后续，notes 注明）、新 ADC 通道/实例（**本批及以后 ADC 类一律薄封装共读 MEM0**——MEM 槽位 8/8 已满）。
- 正文内嵌段落（行拆散版）不作为提炼源。
- 七件 DO 数字量阈值读取（LM393 阈值由模块可调电阻控制，页面 DO 函数未用于演示——mq2 同策略不声明，需要时经引脚绑定 GPIO 输入自读）。
- ppm 级精确标定（MQ 系/MS1100 为相对值，需标准气体标定）、湿度/温度补偿（页面未实现）。
- MQ-9 双温循环（低温 CO/高温可燃气）的加热控制与双通道标定（4Pin 模块无加热控制脚、页面驱动仅单 AO——notes 说明）。
- MS1100 页面「采集到的电压与甲醛甲苯对应关系」图片换算表（无图注素材、未落码——真机标定留用户）；3-5 分钟预热等待归调用方。

## 补充说明

- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 2026-09-11 复跑：真缺 12 篇（nrf24l01、8 篇彩屏、1.3 单色、mpu6050）——本批七件均在全自洽 58 篇内。
- 工单：`issues/01-module-mq3.md` → 02 mq4 → 03 mq6 → 04 mq7 → 05 mq8 → 06 mq9 → 07 ms1100（互相独立、无共享 ADC 演进（薄封装无 syscfg 改动）；实施按简→繁：mq3-09 六件同构照抄 mq2 → ms1100（页面无百分比函数，推导 read_percent））。
- **code-review 裁决（同构批量豁免逐件深审）**：随机抽 2 件（实现时以提交前随机种子定，如按时间戳取模）做双轴深审；其余 5 件按「与 mq2/已深审件同构对仗核对」（结构字段逐条比对 + 守卫断言过测试 + 编译矩阵 PASS 即视为通过），豁免结论记入本 spec 实施结论。
- 完成后：全量测试套件 + 批次 1-11 全部 46 件一致性快检（`.scratch/wiki-modules-batch11/sweep_46_modules.py`）+ CONTEXT.md 平台行补录七件（MQ 系同构快补收尾——全部薄封装共读 MEM0、正向映射、现实约束）+ 中文提交（.githooks/commit-msg 强制中文；无新增 .ps1——如新增按 UTF-8 with BOM 存）。
- 词表预算（待实测，实施前先量）：七件入库后默认词表完整 wire 将超 6634（WORDLIST_PROMPT_BYTES=6800 的 fit 上限 6800−166）——按批次 5/6/7/8/9/10 先例实测后上调 WORDLIST_PROMPT_BYTES 并同步 budget.py/llm.py 记账注释与 REFERENCE_FULLTEXT_BYTES（保 2KB 边界余量，结构测试红线见 tests/test_llm.py::test_selection_prompt_worst_case_fits_request_budget 与 test_wordlist_segment_covers_default_wordlist_and_budget）。

## 实施结论（2026-09-11，收尾补记）

- 七件编译矩阵全部 PASS（0 error/0 warning）：mq3、mq4、mq6、mq7、mq8、mq9、ms1100——单选生成 → SysConfig CLI → gmake 真编译；verified=true 全部回写（notes 含编译记录）；未上板（notes 注明）。
- 方向定稿：七件全部**正向映射 value/4095×100**（页面原式 + 正文取证，与 mq2 定稿方向一致）；ms1100 页面无百分比函数——read_percent 由页面 demo 电压式 value/4095×3.3 推导归一（Vref 3.3V，notes 记录推导）；无 rain 式正文/公式矛盾。
- 词表预算实测：七件（模型+方案名）入库后默认词表完整 wire **7051**（> 6634 fit 上限 6800−166——test_wordlist_segment 契约红证）→ WORDLIST_PROMPT_BYTES **6800→7300**（fit 上限 7134 ≥ 7051 全量送达 + 83B 余量）；词表段全量 7051 比旧截断形态 6634 多 417B → REFERENCE_FULLTEXT_BYTES **61000→60500** 保 2KB 边界余量（batch5/7/8/9 口径；llm.py/budget.py 记账链同步，worst-case 结构测试绿）。
- 46 件一致性快检（sweep_46_modules.py）全 OK；全量测试 **3528 pytest + 1358 node:test 全绿**（无新增 .ps1）。
- 工单 01-07 全部实施完毕并标记 resolved（结论含提交号/关键发现）。

## code-review 结果（2026-09-11，双轴并行评审，固定点 HEAD；随机抽 ms1100/mq8 深审 + 其余 5 件同构对仗核对——同构批量豁免逐件深审）

- **标准轴**：无代码/文档层硬违规，唯一流程项 = 工单 resolved/提交（已完成）。深审 ms1100/mq8 全过（notes 五要点齐全、公式逐字对页、kit/source_url/网盘链接全部核实、无 IRQHandler 回潮、简介四要素齐、ADR 0009 纯驱动、中文合规）；mq3/4/6/7/9 归一化后与 mq8 零结构分歧（仅注释措辞差异，均与各页核实）。判断项 4 件已整改：① ms1100 manifest notes 去「LM393 比较」外推（页面仅述可调电阻比较）；② mq4/6/7/8/9 manifest notes 记录页面 Get_MQx_DO_value 注释「酒精值」模板残留错字（MQ-3 页复制残留，未用于演示不落码；mq3 本件该注释正确无需记录）；③ wordlist MQ-3/4/6/7/8/9 供电口径 5V→**3.3-5V**（与页面/kit 一致；ms1100 页面即 5V 保留）；④ test_module_mq8 尾随空白、test_module_ms1100 双空行清理。Smell 观察：Duplicated Code / Shotgun Surgery / Data Clumps = repo 先例覆盖（ADR 0008 独立复制单元、spec 同构照抄、批次管线既定），不作硬违规。
- **规格轴**：无功能级硬伤；缺漏 3 处已整改——(a)1 mq9 manifest notes 补「器件双温循环 + 4Pin 无加热控制脚 + 双通道区分需模块级温控/标定 + 与 mq7/mq6 分工」；(a)2 mq7 manifest notes 补「高低温循环检测但 AO 单路输出（4Pin）」；(c)1 mq9 引文失真（省略号省去方向论据、"与代码一致"不符代码行为）→ 改为方向取证「电导率随 CO 浓度增加而增大」+ 双温限制另注（manifest 与 mq9.h 同步）。(b) 范围蔓延提示：`.scratch/wiki-md-repair/issues/05/06` 两文件系另一流水线残留——本批提交显式排除。
