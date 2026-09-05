# 批次 2「传感器常用」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1「遥控/通信」四件（joystick/hc05/nrf24l01/ir_remote）已于 2026-09-05 入库（wiki-modules-batch1/01-04）。`lckfb-地猛星移植手册/` 剩余 66 篇中约 58 篇页内自带完整驱动源码（v7 审计自包含），模块库仍没有对应条目——用户做控制题选传感器件时 AI 不知道库里有驱动，只能当"需自备"。

按用户裁决：批次 2 = **传感器常用**四件——DHT11 温湿度（单总线）、US-016 超声波（模拟量输出）、BH1750 光照度（软 I2C）、红外测距 GP2Y0A02（模拟量 ADC）——全部页内源码完整（v7 全自洽）、无需网盘。

## 方案

照批次 1 已确立管线，每件一个工单：手册「代码块」提炼完整 bsp（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机）→ 母版 syscfg 新实例 / 共享实例登记 + `syscfg_instances.py` INSTANCE_CONSUMERS 登记 → manifest（dependencies/pins/kit+source_url/notes 含手册路径+原页+网盘链接+改造要点）→ wordlist.json 对应分类补录（lib_modules 挂接）→ 测试（`test_module_<slug>.py` 照 test_module_joystick.py 模板 + test_pins.py / test_pin_bindings.py / test_syscfg_prune.py 增断言）→ 编译矩阵（复制 run_joystick_matrix.py 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified=true 回写 → 中文提交 → 逐件 code-review。

## 用户故事

1. 作为做题用户，我选中 `dht11`/`us016`/`bh1750`/`ir_distance` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + 服务函数读温湿度/距离/光照度。
2. 作为做题用户，我做环境监测题（温湿度+光照）、避障题（模拟量超声/红外测距）时不用再读器件手册、不用自写时序。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/编译记录），可溯源到手册。

## 实现决策

### 共性（四件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 `bsp_*.c/h`，改造为 `xxx_init()` + 服务函数，去 main/printf，函数名规范化（去 `Get_`/`DHT11_Read_Data` 菜市场命名），全局状态收敛为模块内静态 + 出参指针。
- **时序**：微秒/毫秒延时全走库内 `delay` 模块（页外 `delay_uus` 工具函数替换，同 ws2812 先例）；**不占 TIMER 实例**（TIMG0/6/7/8/12 已被全占，sr04 先例）。
- **ADC 中断改轮询**：手册的 `ADC12_0_INST_IRQHandler` + 标志位按 joystick 先例改 `DL_ADC12_getStatus` 忙等——多模块同选会链接期重复定义同一个 `ADC12_0_INST_IRQHandler` 强符号，轮询是唯一可组合形态。
- **引脚宏参数化**：按 manifest pins 角色 + 母版 syscfg 实例宏名对齐（`<实例>_<引脚名>_PIN`/`_IOMUX` 命名，aht10 编译矩阵实测）。
- **默认脚**：地猛星 2×20 排针 31 个 IO 全被默认布局占用 → 新模块默认脚按「同选概率最低者与既有默认重叠」分配，同选经引脚绑定消解；重叠对写入 `test_pin_bindings` 刻意重叠表。
- **wordlist**：感知传感器组按条目补录（名称 + `lib_modules` 挂接），硬件词表 models 加词条。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `dht11` | sensor--dht11-temp-humi-sensor.md | 1 × GPIO 双向（单总线位时序） | 新 GPIO 实例 `DHT11`/DATA（OUTPUT、initialValue SET——空闲高电平） | 微秒延时走 delay 模块（delay_ms(19)/delay_us(20/28/1)，页外 delay_uus 替换）；数据线运行时切换方向（aht10 SDA 先例）；默认 DATA=PB7——与 AHT10 SDA（温湿度互替，同选概率最低）/STEP_MOTOR DIR2/HUIDU R4 重叠，同选经引脚绑定消解；校验和失败/超时返回失败 |
| `us016` | sensor--us-016-ultrasonic-ranging-sensor.md | 模拟量输出（ADC 电压→距离） | 无新实例——**依赖 adc 模块 MEM0 的薄封装**（ADC12_0 已是 sequence 三通道：MEM0=adc、MEM1/2=joystick） | `dependencies: ["adc"]`，读 MEM0（adc_get(ADC_1, ADC_Channel_0)）；手册原脚 PA27 因 MEM0 槽位默认 PA24 不可用——绑定到 PA27 即复现手册接线（绑定改写 adcPin3→adcPin0 + adcMem0chansel→CHAN_0）；距离公式 L=(A×3072/4096)×(Vref/Vcc)mm（手册正文「3096」与代码「3072」不一，按代码 0.75 系数）；50 次×10ms 平均改 5 次快速平均（joystick 先例） |
| `bh1750` | sensor--bh1750-light-intensity-sensor.md | 软 I2C（2 GPIO，SDA 方向运行时切换） | 新 GPIO 实例 `BH1750`/SCL+SDA（照 AHT10 先例，不占硬件 I2C 外设） | 软 I2C 照 aht10 先例（SDA_OUT/IN 运行时切换，半周期 2us；依赖 delay）；默认 SCL=PA12/SDA=PA13——与 PWMAB C0/C1（motor PWM）重叠（光照度监测/台灯与双电机驱动同选概率最低）；地址 0x46（ALT 接地）；读数 /1.2 出 lx；（0x10 连续高分辨率，测量 120ms 由调用方延时） |
| `ir_distance` | sensor--Infrared-distance-sensor.md | 模拟量输出（ADC 电压→距离） | ADC12_0 **sequence 加第 4 通道**（endAdd 2→3；MEM3=PA27/A0_0） | 通道策略同 us016——MEM0 已被 us016 薄封装占用，us016 与 ir_distance 同属测距互替件但同选需求（双传感器）无法经绑定消解同一槽位 → 本件走独立通道：adcMem3chansel=CHAN_0 + adcPin0=PA27（**手册原脚**）+ endAdd=3（SysConfig 多 MEM sequence 实证先例）；默认 PA27 与 HUIDU R2 重叠（红外测距与 8 路灰度巡线同选概率最低）；轮询读 MEM3（照 joystick 直接读实例，dependencies 空）；公式 60.374×pow(V,−1.16)（GP2Y0A02YK0F，V 按 4095/3.3V），10 次平均保留手册值；4 通道共享事实同步更新 joystick 相关测试断言与 adc 模块注释 |

### 通道细节（us016 / ir_distance 与 ADC12_0 共享）

- 现状：`ADC12_0` sequence，startAdd=0/endAdd=2，MEM0=PA24/A0_3(adc)、MEM1=PA26/A0_1(joystick X)、MEM2=PA25/A0_2(joystick Y)。
- us016 = 薄封装：默认脚 = MEM0 槽位脚 PA24（无新 $assign 行）；角色 id `US016_OUT_CH0`（尾 `_CH<N>` 推导 MEM 索引，syscfg_model 原语）。
- ir_distance = 独立通道：母版 syscfg 增 `adcMem3chansel="DL_ADC12_INPUT_CHAN_0"` + `adcPin0.$assign="PA27"` + `endAdd=3`；角色 id `IR_DIST_OUT_CH3`。
- INSTANCE_CONSUMERS：`"ADC12_0": ("adc", "joystick", "us016", "ir_distance")`。
- 两件均轮询、不注册 `ADC12_0_INST_IRQHandler`（共享实例 + 中断强符号唯一性）。

### 网盘依赖（本批无）

本批四件页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞：全部未上板（时序/换算系数真机验证留后续）。

## 测试决策

照批次 1 先例逐件：

- `tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射（dht11 DATA、bh1750 SCL/SDA 三组 GPIO 角色；us016/ir_distance 的 adc 角色无 GPIO 组/外设字段落点，由 test_pin_bindings 落点唯一性覆盖）；
- `tests/test_pin_bindings.py` 刻意重叠表更新（PB7 3→4、PA12 1→2、PA13 1→2、PA27 1→2、PA24 注释注明 us016 共享槽位）；需同步核查 joystick 相关共享断言（无 endAdd 断言需改，注释同步）；
- `tests/test_syscfg_prune.py` 增 DHT11/BH1750 实例与 ADC12_0 新消费方（us016/ir_distance）保留/裁剪断言；
- 新增 `tests/test_module_dht11.py` / `test_module_us016.py` / `test_module_bh1750.py` / `test_module_ir_distance.py`：manifest 结构 + 单选生成（syscfg 含实例 + 模块文件落盘 + main.c 调 init/服务函数过静态门禁）；
- 编译级验收：复制 `run_joystick_matrix.py` 改 slug，gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- 其余传感器批次（气体/气压/色彩/触摸/微波雷达/指纹等）另立工单；彩屏 + 0.96 SPI 单色需网盘（批次 7 先例）。
- stm32 平台条目、上板真机验证（真机留后续，notes 注明）、新 ADC 外设实例（ADC0 唯一，共享消解先例不开新实例）。
- 正文内嵌段落（行拆散版）不作为提炼源。
- 动辄 500ms 的原文平均采样节拍（us016 50 次×10ms）按 joystick 先例改为快速平均（真机行为差异随 notes 注明）。

## 补充说明

- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 可复跑；本批四件均在 v7 全自洽清单内。
- 工单：`issues/01-module-dht11.md` → 02 us016 → 03 bh1750 → 04 ir_distance（实施按简→繁；ir_distance 放最后——母版 sequence 加通道影响面最大，需同步共享事实）。
- 完成后：全量测试套件 + 批次 1+2 全部 8 件 code-review 收尾 + CONTEXT.md 平台行补录 + 中文提交。
