# 批次 5「ADC 薄封装群一」— 立创 wiki 地阔星 STM32F103C8T6 手册模块批量入库（stm32 线）

## 问题陈述

stm32 线进度：批次 1-4 已入库 22 件（GPIO 6 + 软 I2C 总线 6 + 器件库 6 + 气压/单总线 4；vl53l0x 待资料）。本批 = **ADC 模拟量薄封装群一**：mq2/mq135/mq5（气体）、photoresistance/rain/s12sd/soil（环境量）、gp2y1014au（粉尘+LED 脉冲）——8 件全为「AO 模拟量 + 百分比/档位换算」同构形态（页面 3 代码块），是 mspm0 线批 2/6/7/9/11 的 stm32 对应。

**stm32 侧通道现实（与 mspm0 不同）**：C8T6 排针可达 ADC 通道 10/10 全被既有角色占用（PA0/1=adc+motor PWM、PA2/3=DEBUG、PA4=microwave+ENC、PA5=flame、PA6/7=I2C 总线、PB0=hx711、PB1=ds18b20）——**无空闲通道**。故本批 8 件全部按「**薄封装共读**」口径（mspm0 MEM0 共读同构）：默认 AO = **ADC_Channel_5（PA5）**（页面原脚 8/8 = PA5——即插即用；与 flame 默认共读；ml_adc 顺序调用无扰）；多件同选 = 同一物理脚只能接一件器件（模拟源混叠）→ 现实约束 notes（需外部分路器/分时切换，与 mspm0「MEM 满后」同口径）。

## 方案

照批次 1-4 管线。每件：页面「代码块」提炼 → 纯驱动切片（`<slug>_init()` + 服务函数，API 与 mspm0 全对齐：同函数名/同出参/同失败码）→ **页面 ADC 序列代码全部收敛为 ml_adc**（`adc_init(ADC_1, <SLUG>_AO_CH)` + 5 次 `adc_get` 快平均；RCC/序列由 ml_adc 内定）→ pin_config.h 新宏（`<SLUG>_AO_CH` = ADC_Channel_5；gp2y 另有 `GP2Y1014_LED_GPIO/PIN` 2 宏）→ manifest（pins `<SLUG>_AO` type adc + macros；依赖 ["adc","delay"]（照 mspm0 manifest 现状））→ 测试 → UV4 矩阵 0/0 → verified → 中文提交。

## 用户故事

1. 做题用户选 stm32 + mq2/mq135/mq5/photo/rain/soil：`init()` + `read_percent()` 直接出 0-100% 相对量（页面原式 + 正文取证），不再「需自备」。
2. 做题用户选 stm32 + s12sd：`read_uv_index()` 出 0-11 档（档位表逐档常量单源）。
3. 做题用户选 stm32 + gp2y1014au：`read_dust()`（10ms LED 脉冲周期内置，280us 采样窗）+ LED 脚自动驱动。
4. 维护者：每件可溯源（source_url=wiki 原页 + notes 手册路径/网盘/修正记录/通道现实约束）。

## 实现决策

### 既定事实（勿重新调研；batch5-facts.md 已取证，8 页全 F1 零 F4）

① **页面原脚全 PA5（ADC1_CH5）**，DO 脚 = PA1×4（仅宏未用）/PA2/PA6，s12sd/gp2y 无 DO；本批 8 件默认 AO 全 = ADC_Channel_5（PA5，与 flame 共读——薄封装共读点）；页面原脚即采用（与 mspm0「MEM0 共读」成因不同——stm32 无 MEM、通道 10/10 全占，共读是唯一口径）。
② **修正项（本批仅 2 处与 mspm0 批 9 不同/需特判）**：
   - **rain 公式方向**：页面原式 `(1−value/4095)×100` 与正文 L50「雨越大数字值越大」矛盾 → 按正文改正向 `value/4095×100`（mspm0 批 9 同款修正；守卫「rain 的 `1.0f - ` 不得出现在 percent 公式」）；photoresistance 反向 `(1−value/4095)×100` 与「最亮 100 最暗 0」**自洽——保留**（本批唯一反向自洽页）。
   - **gp2y SAMPLES/周期矛盾**：页面 SAMPLES 30×2ms≈62ms ≫ 10ms LED 周期 → 5 次快平均（照 mspm0）；时序常量参数化（280us/40us/9680us 宏族照 mspm0）。
③ **DO 全不声明**（6 页 DO 宏 main 演示未用——LM393 阈值可调电阻，mspm0 批先例；notes）；**s12sd 档位表 0-11 级**（上界 227/318/408/503/606/696/795/881/976/1079/1170 逐档、5 次快平均——非百分比）；soil 15k 固定衰减 = mspm0 板 PA14 板载负载特例，stm32 侧 PA5 无此问题（notes 澄清）。
④ **gp2y LED 默认脚**：页面原脚 PA2（DEBUG_UART TX 常备件）**不照抄** → 默认 **PB5**（gp2y LED 输出（低有效脉冲）与「称重（hx711 SCK）/光电编码器闭环（MOTOR_A_ENC）」不同框；白名单 3 叠登记；同选经绑定消解）。
⑤ **串台/瑕疵登记（notes 级，不落码）**：mq2 L50「PA27」地猛星串台 + L219 原型重复声明、mq135 L185/mq5 L187/soil L186「酒精值/可燃气体」串台、rain L97/102「GPIOC/GPIOE」串台、s12sd L289「IRtracking demo start」串台、soil L138-140 DMA 函数名残留（Get_Adc_Dma_Value）、rain delay_1ms 依赖（→delay_ms）、C99 for 声明（按 C89 改写）、stdio 残余 include ×2、gp2y Filter 全局符号泄漏（收敛 static）。
⑥ **mspm0 API（对齐签名）**：mq2/mq135/mq5/photo/rain/soil = `init()` + `read_percent()`（float；`<SLUG>_ADC_MAX 4095u`、`<SLUG>_ADC_SAMPLES 5u`）；s12sd = `init()` + `read_uv_index()`（uint8 档位 0-11；`S12SD_ADC_SAMPLES 5u`）；gp2y1014au = `init()` + `read_dust()`（float；宏族 `GP2Y1014_FILTER_WINDOW 10u / LED_SETTLE_US 280u / LED_SAMPLE_TAIL_US 40u / LED_CYCLE_TAIL_US 9680u / ADC_SAMPLES 5u`——按 mspm0 .c 实现口径逐行对齐；0.17×value−0.1 系数保持页面/mspm0）。
⑦ **组件依赖**：dependencies = mspm0 manifest 现状（7 件 ADC 件为 ["adc"]、gp2y1014au 为 ["adc","delay"]——照 mspm0 现状照抄；「["adc","delay"] 类」措辞以单项现状为准）；wordlist 已挂接零补录（8 slug mspm0 批入库过）。
⑧ **测试/矩阵**：照 test_module_flame.py（ADC 件 stm32 先例——FLAME_AO_CH 单宏 + adc 依赖 + 单选生成）；STM32_MACRO_VALUES 补 10 宏（8×AO_CH + gp2y LED 2）；test_default_layout 白名单 PA5 组（9 角色——flame+8 件 ADC 共享组登记）+ PB5 +1（gp2y LED）。

### 各件决策（API 与 mspm0 全对齐；默认 AO 全部 = ADC_Channel_5/PA5，白名单共享组登记；页面原脚即采用）

| 工单 | slug | pins（stm32） | API | 修正/notes 要点 |
|---|---|---|---|---|
| 01 | mq2 | `MQ2_AO` adc PA5 [MQ2_AO_CH] | `mq2_init()/mq2_read_percent()` | 正向 value/4095×100；30 次无延时→5 次快平均；L50「PA27」串台+L219 原型重复 |
| 02 | mq135 | `MQ135_AO` adc PA5 [MQ135_AO_CH] | `mq135_init()/mq135_read_percent()` | 正向；L185「酒精值」串台 |
| 03 | mq5 | `MQ5_AO` adc PA5 [MQ5_AO_CH] | `mq5_init()/mq5_read_percent()` | 正向；L187「酒精值」串台 |
| 04 | photoresistance | `PHOTORESISTANCE_AO` adc PA5 [...] | `photoresistance_init/read_percent()` | **反向式保留（自洽）**；DO 未用不声明；stdio 残余剔除 |
| 05 | rain | `RAIN_AO` adc PA5 [RAIN_AO_CH] | `rain_init()/rain_read_percent()` | **方向修正为核心**：正向 value/4095×100（正文）；GPIOC/GPIOE 串台；delay_1ms→delay_ms；C99 for 改写 |
| 06 | s12sd | `S12SD_AO` adc PA5 [S12SD_AO_CH] | `s12sd_init()/s12sd_read_uv_index()` | 档位表 0-11 逐档；L289 IRtracking 串台 |
| 07 | soil | `SOIL_AO` adc PA5 [SOIL_AO_CH] | `soil_init()/soil_read_percent()` | 正向；DMA 注释残留；「可燃气体」串台；stm32 无 15k 衰减问题澄清 |
| 08 | gp2y1014au | `GP2Y1014_AO` adc PA5 [GP2Y1014_AO_CH] + `GP2Y1014_LED` gpio_out **PB5** [GP2Y1014_LED_GPIO/PIN] | `gp2y1014_init()/gp2y1014_read_dust()` | **SAMPLES/周期矛盾→5 次快平均**；LED 原脚 PA2 弃用→PB5；时序宏族参数化；Filter 收敛 static |

### 默认脚与重叠全景（定稿）

| slug | 默认脚 | 重叠主体（同选概率最低） |
|---|---|---|
| mq2/mq135/mq5/photo/rain/s12sd/soil | AO=PA5 | flame（**ADC 共享组**：8+1 件全 adc 类型同脚 → `_shared_groups` kind=share「ADC 通道共享」；现实约束 = 同一物理脚只能接一件器件，多件同测需外部分路器——notes，mspm0 MEM 满后同口径 |
| gp2y1014au | AO=PA5 + LED=PB5 | AO 同上；LED 叠 hx711 SCK + MOTOR_A_ENC（粉尘与称重/编码器闭环不同框） |

- **9 件默认 AO 共读 PA5**（flame + 8 件）——白名单 PA5 组登记（ADC 共享组，注释批次 5 + 物理约束）；**页面原脚即采用**（无弃用记录——与批 2-4 不同，本批页面原脚恰为共读点）。
- PB5 白名单 +1（gp2y LED——现 hx711 SCK + MOTOR_A_ENC）。

## 测试决策

- 新增 8 个 `tests/test_module_<slug>.py`（照 test_module_flame.py 模板——ADC 件 stm32 先例）：manifest 形状（pins 元组/macros/依赖 ["adc","delay"]/kit/source_url/notes 子串）+ 母版宏存在断言（`#define <SLUG>_AO_CH\s+ADC_Channel_5`、gp2y `GP2Y1014_LED_GPIO\s+GPIO_B`/`_LED_PIN\s+Pin_5`）+ stm32 单选生成全流程 + mspm0 零改动守卫 + 缺陷守卫：
  - 通用：`ADC_Channel_5` 宏、`* 100.0f`/`4095u`、无 printf/GPIO_Init/RCC_/delay_1ms、无 DO 说明（`DO` 不出现 pins）；
  - rain：**`1.0f - ` 不得出现**（正向映射防回潮）+ 正文方向注释；photoresistance：**反向 `1.0f - ` 必须出现**（自洽保留守卫——两件反向断言对仗）；
  - s12sd：档位表 0-11 上界常量（227…1170）+ `S12SD_ADC_SAMPLES 5u`；
  - gp2y：`280u`/`40u`/`9680u` 时序宏 + `ADC_SAMPLES 5u`（无 30）＋ LED 宏。
- `tests/test_pins.py` STM32_MACRO_VALUES 补 10 宏；`tests/test_default_layout.py` 白名单：PA5 组（ADC 共享组 9 角色登记）+ PB5 +1。
- **UV4 矩阵**（每件，照 run_aht10_matrix.py 配方；MAIN_C 调 init + read_percent/read_uv_index/read_dust，(void) 化）→ 0 error/0 module warning → verified=true。
- 词表预算链：零补录（复核即可）。

## 范围外

- mspm0 条目改动（零改动）；B 类新模块；C 类核对（批 11）；vil53l0x（批 4 待资料）。
- 真机验证（未上板 notes——百分比相对值/粉尘 0.17 系数/档位表阈值真机校准留后续）；ppm 精标不承诺（相对百分比）。
- 多 ADC 件多路同测（外部分路器方案不落码——notes 现实约束）；DO 数字量（阈值可调电阻，骨架可经 gpio 直读）。
- soil/s12sd 的「校准时序」（归调用方）；gp2y 滑动窗口滤波实现口径 = 照 mspm0 .c（FILTER_WINDOW 宏如 mspm0 用则照用）。

## 补充说明

- 排序：01 mq2（打样）→ 02 mq135 → 03 mq5 → 04 photoresistance（反向自洽对照）→ 05 rain（方向修正核心件）→ 06 s12sd（档位表）→ 07 soil → 08 gp2y1014au（LED+时序最重）；同构批量可随机抽 2 件深审 + 其余结构对仗（mspm0 批 11 裁决）。
- 页内事实 = %TEMP%\batch5-facts.md（1df0abcf 报告，2026-09 回填）。
- 收尾清单：全量测试 → sweep 更新 → code-review 两轴 → CONTEXT 补录 → 中文提交。
