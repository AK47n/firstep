# 批次 8「环境类第二组（火焰/土壤 + GPIO 传感）」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1-7 共 27 件已入库（遥控/通信、传感器常用、显示/执行、语音/身份、I2C 增强件、环境监测/温度补充第一组、气体/空气传感器第一组）。`lckfb-地猛星移植手册/` 剩余页中**环境类第二组**四篇页内自带完整驱动源码（v7 审计自包含，`.scratch/wiki-materials/audit_v7.py` 自包含清单已确认）：火焰传感器（LM393 模拟输出）、土壤湿度传感器（模拟 + DO 阈值）、人体红外感应（GPIO 迷你驱动）、微波多普勒雷达（GPIO 迷你驱动）——模块库仍无对应条目：用户做灭火小车/火警报警、自动浇花/智慧农业、人来灯亮/防盗报警、自动门/车流检测题时，AI 不知道库里有驱动，只能当"需自备"。

按用户裁决：批次 8 = **环境类第二组**四件——全部页内源码完整（v7 全自洽）、无需网盘。

## 方案

照批次 1-7 已确立管线，每件一个工单：手册「代码块」提炼完整 bsp（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机——微波页面开/关门时序演示归生成骨架）→ 母版 syscfg（ADC 件 = 改 ADC12_0 通道/endAdd；GPIO 件 = 新 GPIO 输入实例）+ `syscfg_instances.py` INSTANCE_CONSUMERS 登记 → manifest（dependencies/pins/kit+source_url/notes 含手册路径+原页+网盘链接+改造要点+极性说明）→ wordlist.json 补录（感知传感器，lib_modules 挂接；火焰/土壤湿度/人体红外/微波雷达与既有环境件并列）→ 测试（`test_module_<slug>.py` 照 test_module_mq135.py / test_module_ttp224.py 模板 + test_pins.py / test_pin_bindings.py / test_syscfg_prune.py 增断言；ADC 换通道后旧断言全量同步）→ 编译矩阵（复制 run_mq135_matrix.py 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified=true 回写 → 中文提交 → 逐件 code-review。

## 用户故事

1. 作为做题用户，我选中 `flame`/`soil`/`human_ir`/`microwave_radar` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + 服务函数读火源/土壤湿度/人体/移动。
2. 作为做题用户，我做灭火小车/火警联动（火焰 + 报警 + 气体）、自动浇花（土壤 + 泵）、感应灯/防盗（人体红外 + 灯光/报警）、自动门/车流检测（微波 + 门控）时，不用再读器件手册、不用自写读取时序。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/极性宏/编译记录），可溯源到手册。

## 实现决策

### 既定事实（勿重新调研，批次 1-7 已实证）

① ADC12_0 sequence 六通道（endAdd=5：MEM0=adc/us016/mq2 薄封装共读、MEM1-2=joystick X/Y、MEM3=ir_distance、MEM4=mq135（通道6 PB20）、MEM5=mq5（通道5 PB24）；地猛星板上 ADC0 可用通道/脚 = CH0=PA27/CH1=PA26/CH2=PA25/CH3=PA24/CH5=PB24/CH6=PB20/CH7=PA22/CH12=PA14，A1_* 组设备数据不可用；**2026-09-08 SysConfig CLI 实证** MEM4-7 通道/脚（adcPin6=PB20/adcPin5=PB24/adcPin7=PA22/adcPin12=PA14）全部被 CLI 接受）；② SysConfig 拒绝同一 UART 外设多实例——本批无 UART 件；③ 地猛星 2×20 排针 31 个 IO 全被默认布局占用——新模块默认脚按「同选概率最低者与既有默认重叠」，同选经引脚绑定消解；④ 母版 GPIO 中断全走 GROUP1 单向量且被 motor 编码器独占——本批全部轮询，不注册中断（页面同为电平直读）；⑤ 软 I2C/软 SPI/软 UART/忙等不占 TIMER 先例——本批无时序件（火焰/土壤 = ADC 轮询、人体红外/微波 = 电平直读），**零 delay 依赖**；⑥ 工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`；⑦ 页内符号异常/器件正确性缺漏→人工复核、修正并记 notes（ir_remote 反码校验、nrf24l01 缺陷、sgp30 CRC8、ags10 重试写反先例）；⑧ 一致性快检脚本先例 `.scratch/wiki-modules-batch6/sweep_23_modules.py` → 本批后更新为 31 件版（`.scratch/wiki-modules-batch8/sweep_31_modules.py`）。

### 共性（四件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 bsp，改造为 `xxx_init()` + 服务函数，去 main/printf/DEMO 时序，函数名规范化（去 `ADC_FLAME_Init`/`Get_Adc_FLAME_Value`/`Get_FLAME_Percentage_value`/`Get_HumanIR`/`OUTPIN_Scanf` 菜市场命名按库风格重命名），全局状态收敛为模块内静态。
- **引脚宏参数化**：按 manifest pins 角色 + 母版 syscfg 实例宏名对齐（`<实例>_<引脚名>_PIN` + `<实例>_PORT`——实例内单脚时生成 `HUMAN_IR_PORT`/`HUMAN_IR_OUT_PIN`，aht10/ttp224 先例）。
- **默认脚**：按「同选概率最低者与既有默认重叠」分配（冲突矩阵见下）；四件默认**互不相撞**（火警/浇花/感应/移动检测环境站组合，默认即不撞）；重叠对写入 `test_pin_bindings` 刻意重叠表。
- **wordlist**：感知传感器组补录四件（名称 + `lib_modules` 挂接），models 加词条。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `flame` | sensor--flame-sensor.md | ADC 模拟量（AO 输出，红外光越强 ADC 值越小） | **无新 GPIO 实例**——ADC12_0 **sequence 开 MEM6**（**endAdd 5→6**、`adcMem6chansel=CHAN_7`、`adcPin7=PA22`） | 火焰 = **ADC 独立 MEM6**（mq135/mq5 模式）——MEM 倒数第二槽；页面原脚 PA27（A0_0）已归 ir_distance MEM3。API = `flame_init` + `flame_read_percent`（出 float 0-100% 火焰强度百分比——页面原式 `(1 - value/4095)×100` **反向映射**（红外越强数值越小→百分比越高），5 次快平均照 mq2，页面 30 次累加太慢）；读数经 adc 模块 API（`adc_get(ADC_1, ADC_Channel_6)`——busy 忙等单点实现在 adc 模块）；页面 ADC 中断（IRQHandler + gCheckADC）改依赖 adc 模块轮询（无 IRQHandler 强符号）；页面 `Get_FLAME_Do_value`/`GET_DO` 宏（LM393 阈值比较）**不声明 DO 角色**（mq2/mq135/mq5/soil 同策略——阈值由模块可调电阻控制，需要时经 GPIO 输入自读，notes 说明）；notes 写明**火焰范围为 700-1000nm 红外**（对日光/热源会误判，探测角度 60°、灵敏度峰值 880nm——页面规格参数）与换向换算说明。角色 id `FLAME_AO_CH6`（尾 `_CH<N>` 推导 MEM 索引，ir_distance 先例） |
| `soil` | sensor--soil-moisture-sensor.md | ADC 模拟量（AO 输出，水分越足电导越高 ADC 值越大） | 无新 GPIO 实例——ADC12_0 **sequence 开 MEM7**（**endAdd 6→7**、`adcMem7chansel=CHAN_12`、`adcPin12=PA14`） | **最后一个 MEM 槽位（8/8 用满）**——后续 ADC 类（photoresistance/rain/gp2y1014au/s12sd/ms1100）一律薄封装共读 MEM0 模式（mq2/us016 先例，notes 写明多器件共读限制）。API = `soil_init` + `soil_read_percent`（出 float 0-100%——页面原式 `value/4095×100`（页面 Get_SH_Percentage_value 直接正比，非火焰的反向映射），5 次快平均、`adc_get(ADC_1, ADC_Channel_7)`）；页面 ADC 中断改轮询；页面 `Get_SH_DO_value`/`GET_DO` 宏（LM393 阈值比较）**不声明 DO 角色**（同上）；页面页码注释「Get_Adc_Dma_Value」系函数名残留——按实际函数 Get_Adc_Value 收敛为模块内 5 次快平均；notes 写明 15k 负载限制（见冲突矩阵）与灵敏度调节（板载蓝电位器）说明。角色 id `SOIL_AO_CH7` |
| `human_ir` | sensor--human-body-infrared-sensor.md | 1 × GPIO 输入（HC-SR501 热释电，3 Pin） | 新 GPIO 输入实例 `HUMAN_IR`/OUT（direction INPUT、internalResistor PULL_UP） | **GPIO 迷你驱动**（页面 Get_HumanIR 返回 GET 宏 + header + main 完整，照 relay/human-body 提炼先例）。API = `human_ir_init`（空实现占位——SYSCFG_DL_init() 生效，ttp224/ir_beam 先例）+ `human_ir_read`（返回 1=感应到人体、0=未感应到）。**极性定稿：感应到 = 输出高**——模块介绍「人进入其感应范围则输出高电平」+ 规格「电平输出：高3.3V/低0V」为准；页面函数注释「0=感应到、1=未感应到」与介绍/规格矛盾（按 ir_remote 反码校验修正先例人工复核：HC-SR501 器件标准输出高=检测到，页面注释疑与微波页同款复制）→ 修正并记 notes；单宏 `HUMAN_IR_TRIGGER_LEVEL`（默认 1u = 引脚高=感应到）可切（照 ttp224 TTP224_TOUCH_LEVEL 先例，宏放 .h）。无去抖/无 GPIO 中断（GROUP1 仍被 motor 编码器独占，页面同为电平直读——主循环轮询，骨架侧按需滤波） |
| `microwave_radar` | sensor--microwave-doppler-radar-sensor.md | 1 × GPIO 输入（HB100 微波多普勒，3 Pin，OUT 输出） | 新 GPIO 输入实例 `MICROWAVE`/OUT（direction INPUT、internalResistor PULL_UP） | **GPIO 迷你驱动**（页面 OUTPIN_Scanf 返回 OUT_IN 宏 + header + main 完整；页面 main 演示含开/关门时序逻辑——**归生成骨架**（ADR 0009），模块只出 `microwave_radar_init`（空实现占位）+ `microwave_radar_read`（返回 1=检测到移动、0=无移动）。**极性按页面（自一致）**：页面注释 + main 演示均按「0=检测到物体移动、1=未检测到」——默认沿用页面（低=检测到），单宏 `MICROWAVE_TRIGGER_LEVEL`（默认 0u = 引脚低=检测到）可切（同上 ttp224 先例）；实物输出反相改宏 1 即可（notes 说明，未上板待真机验证）。无去抖/无 GPIO 中断（同上）。页面「需 5V 供电、2-16m 连续可调」记 notes |

### 默认脚与重叠全景（2026-09-06 定稿，冲突矩阵）

剩余 ADC 通道只有 **PA22（A0_7/CH7）与 PA14（A0_12/CH12）**（PA27/PA26/PA25 已归 MEM1-3、PB20/PB24 已归 MEM4/5——既定事实①）。四件默认 = **PA22（flame，A0_7/MEM6-CH7）、PA14（soil，A0_12/MEM7-CH12）、PB8（human_ir）、PA31（microwave_radar，见下——PA0/PA1 不可作 GPIO 输入，2026-09-06 SysConfig CLI 实证）**——全部与既有默认重叠、四件互不相撞。

- **flame → PA22**：火焰 AO 直接取自光电二极管端子（页面原文），**高阻电流源**——PA14 板载 LED2+15k 负载会分流（batch7 mq5 判据：不适合作 ADC 模拟输入），故把唯一"干净"通道给火焰；PA22 伙伴 HUIDU L1（巡线）/DEBUG_UART RX/NRF24L01 IRQ/TTP224 OUT1——火警/灭火小车与巡线车、无线链路、触摸面板不同框优先级更高，同选时经引脚绑定消解。
- **soil → PA14**：土壤湿度 AO 为模块分压输出（叉子电阻 + 板载分压），页面换算本就是相对百分比（value/4095×100 单调）——15k 负载为**固定比率衰减**：读数系统性偏小但趋势/单调性保留（相对湿度判定/报警阈值仍可用，notes 写明限制；要求精度时改绑/真机标定）；PA14 伙伴 DCC_100_PWM2（步进）/WS2812（灯带）/RC522 SCK（读卡）/AGS10 SDA（气体）——自动浇花/智慧农业与运动/读卡/气体低频同框、同选概率最低。
- **human_ir → PB8**：与 STEP_MOTOR DCY2（步进）/SR04 ECHO（超声）/AT24C02 SDA（存储记录）重叠——人体红外（感应灯/防盗报警）与步进/测距/记录不同框；刻意不叠温湿度（PB6/PB7/PA7/PA28/PA31）、光照（PA12/PA13）、显示（PB2/PB3）、语音（PB19/PB20）、无线（PA8/PA9/PA23/PA24）、按键触摸（PA2/PA22-27）、蜂鸣（PA15）——感应灯/防盗标配组合。
- **microwave_radar → PA31**：**2026-09-06 SysConfig CLI 实证：PA0/PA1 不在 GPIO 输入实例 pin 选项内**（「cannot set $assign to "PA0": No option named PA0 defined」——GPIO 输出可配 PA0（ir_remote_tx 先例实测仍可过 CLI）、GPIO 输入不可）→ 原拟默认 PA0（板载 LED 指示）作废，改选 PA31：与 IMU601 RX（姿态）/HX711 DT（称重）/FINGERPRINT_UART RX（身份）/SHT30 SDA（温湿度）重叠——微波雷达（自动门/车流/倒车）与姿态/称重/身份/温湿度采集不同框、同选概率最低（自动门/车流惯配电机（PWMAB PA12/PA13）/显示（MAX7219 PA18/PB9/PB18）/蜂鸣（PA15）/无线（PA8/PA9/PA23/PA24）/超声（SR04 脚）/人体红外——刻意不叠）。
- 与既有默认重叠计数（更新 test_pin_bindings.py 刻意重叠表）：PA22 4→5、PA14 4→5、PB8 3→4、PA31 4→5（PA0 保持 2——GPIO 输入不可用，不计入）。
- 本批默认与已入库环境件默认全部错开（气体 PB20/PB24/PA18/PB9/PB18/PA14 中的 PA14 为本批 soil——与 AGS10 SDA 叠但属默认重叠、同选经引脚绑定消解；其余不撞）、与批次 5 八脚仅 PA14 不可避免（通道只剩它）。

### 网盘依赖（本批无）

本批四件页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞：全部未上板（ADC 换算/极性真机验证留后续）。

## 测试决策

照批次 1-7 先例逐件：

- `tests/test_pins.py`：
  - `MSPM0_DEFAULT_MAP` 增 2 条（human_ir OUT → HUMAN_IR/OUT、microwave_radar OUT → MICROWAVE/OUT——GPIO 组角色；flame/soil 的 adc 角色无 GPIO 组/外设字段落点，由 test_pin_bindings 落点唯一性覆盖——mq135/mq5 先例）；
  - `test_module_code_has_no_pin_literals` 豁免元组 `("adc","us016","ir_distance","mq2","mq135","mq5")` 增 `"flame","soil"`（ADC_Channel_N 为 API 对偶枚举）；
- `tests/test_pin_bindings.py` 刻意重叠表更新（PA22 4→5、PA14 4→5、PB8 3→4、PA0 2→3，注释补新件）；
- `tests/test_syscfg_prune.py` 增 HUMAN_IR/MICROWAVE 实例与 ADC12_0 新消费方（flame/soil）保留/裁剪断言；
- 新增 `tests/test_module_flame.py` / `test_module_soil.py` / `test_module_human_ir.py` / `test_module_microwave_radar.py`：manifest 结构（仅 mspm0 + 依赖）+ mspm0 单选生成（syscfg 含实例/通道 + 模块文件落盘 + main.c 调 init/服务函数过静态门禁）；
- **旧断言全量同步**（ADC 换通道）：`test_module_ir_distance.py`、`test_module_joystick.py`、`test_module_mq135.py`、`test_module_mq5.py` 的 endAdd/adcMem/adcPin/docstring 断言随母版演进逐一同步（endAdd 5→6（flame）→7（soil）；adc 模块注释与 `test_module_mq135` 的 `> ADC_Channel_5` 守卫断言同步扩展为 `> ADC_Channel_7`）；
- **关键源码守卫**（防公式/时序/极性走样，ir_remote_tx/mq2 公式守卫先例）：
  - flame：百分比公式守卫（`4095`/`100.0f`、**反向映射 `1.0f - `** 守卫、`ADC_Channel_6`）、无 IRQHandler 守卫（`ADC12_0_INST_IRQHandler`/`gCheckADC` 不得出现）、notes 含「700-1000nm」「反向」；
  - soil：同上（`ADC_Channel_7` 差异、正向 `(float)…/4095` 守卫）、notes 含「15k」「相对百分比」；
  - human_ir：极性宏守卫（`HUMAN_IR_TRIGGER_LEVEL 1u`、`level == HUMAN_IR_TRIGGER_LEVEL`）、notes 含极性修正说明（页面注释 0=感应到 与模块介绍矛盾，按高=感应到修正 + 单宏可切）；
  - microwave_radar：极性宏守卫（`MICROWAVE_TRIGGER_LEVEL 0u`——页面低=检测到）、`1u << `? 无（单脚）；read 语义守卫（`1 = 检测到移动`）；notes 含页面开/关门时序归骨架说明。
- 编译级验收：复制 `run_mq135_matrix.py` 改 slug（四件各一，放 .scratch/wiki-modules-batch8/），gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- stm32 平台条目、上板真机验证（真机留后续，notes 注明）、新 ADC/TIMER/GPIO 中断实例（本批 ADC12_0 加 MEM6/MEM7 用满 8/8——**后续 ADC 类件一律薄封装共读 MEM0**；GPIO 实例照旧加）。
- 正文内嵌段落（行拆散版）不作为提炼源。
- 火焰/土壤 DO 数字量阈值读取（LM393 阈值由模块可调电阻控制，页面 DO 宏/函数未用于演示——同 mq2 策略不声明，需要时经 GPIO 输入自读）、ppm/绝对精度（火焰 = 相对强度 %、土壤 = 相对湿度 %，notes 说明）。
- 微波雷达页面演示的开/关门时序逻辑（flag/time 计时）——归生成骨架（ADR 0009），模块只出 init/read。
- HC-SR501 可重复/不可重复触发跳线、延时调节（板载旋钮）、上电 1 分钟初始化说明——记 notes，不落代码。
- 后续批次地图（另立工单）：9 = ADC 薄封装群（photoresistance/rain/gp2y1014au/s12sd/ms1100——**全薄封装共读 MEM0**，无需新槽，5 件可一批或拆两批）；10 = 剩余杂项（l298n、jy61p、open-mv4、sht20 + mq-3/4/6/7/8/9 同构快补，软 I2C/软 UART 依页面）；11 = 彩屏线（需你下载网盘厂家例程后开工：0.96/1.3/1.47/1.69/1.28 圆屏/1.8 触摸 + 0.96 SPI 单色，链接在 sources/materials/lckfb-地猛星移植手册/网盘索引.md——若已下载好随时插队）。

## 补充说明

- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 可复跑；本批四件均在 v7 全自洽清单内。
- 工单：`issues/01-module-flame.md` → 02 soil → 03 human_ir → 04 microwave_radar（顺序依赖：01/02 共享 ADC12_0 演进（endAdd 5→6→7）串行；03/04 独立可并行；实施按简→繁：flame（独立 MEM 打样 + adc 模块扩展）→ soil（同构照抄、MEM 用满）→ human_ir（GPIO 迷你驱动）→ microwave_radar（同构照抄））。
- 完成后：全量测试套件 + 批次 1-8 全部 31 件一致性快检（sweep_31_modules.py）+ CONTEXT.md 平台行补录四件 + **「MEM 槽位已满（8/8）」决策写入本 spec 与 CONTEXT** + 中文提交（.githooks/commit-msg 强制中文；无新增 .ps1）。
- 词表预算：四件入库后默认词表 wire 实测将超 WORDLIST_PROMPT_BYTES 5700（批次 7 后全文 5495/上限 5534，余 39B）——按批次 5/6/7 先例实测后上调预算并同步 budget.py 注释与全文预算边界（结构调整红线，见 tests/test_llm.py 最坏形态；配套降 REFERENCE_FULLTEXT_BYTES 500B 口径）。
