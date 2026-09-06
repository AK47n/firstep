# 批次 9「ADC 模拟量薄封装群（光敏/雨滴/粉尘/紫外线）」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1-8 共 31 件已入库（遥控/通信、传感器常用、显示/执行、语音/身份、I2C 增强件、环境监测/温度补充第一组、气体/空气传感器第一组、环境类第二组）。`lckfb-地猛星移植手册/` 剩余页中**环境类第三组——ADC 模拟量薄封装群**四篇页内自带完整驱动源码（v7 审计自包含，`.scratch/wiki-materials/audit_v7.py` 2026-09-09 复跑确认四篇均在 58 篇全自洽名单内）：光敏电阻（模拟量）、雨滴检测（模拟 + DO）、GP2Y1014AU 粉尘（模拟 + 内置平均）、S12SD 紫外线（模拟）——模块库仍无对应条目：用户做光控调光/雨感雨刷、扬尘监测/空气净化、紫外线指数检测题时，AI 不知道库里有驱动，只能当"需自备"。

按用户裁决：批次 9 = **ADC 模拟量薄封装群**四件——全部页内源码完整（v7 全自洽）、无需网盘。

## 方案

照批次 1-8 已确立管线，每件一个工单：手册「代码块」提炼完整 bsp（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机）→ **ADC 类一律薄封装共读 MEM0**（无新 ADC 通道/实例/无新 `$assign` 行——mq2/us016 先例；gp2y1014au 例外见下）→ `syscfg_instances.py` 按 mq2 登记方式核对（薄封装仅 ADC12_0 消费表加 slug；gp2y1014au 另登记 GPIO 实例）→ manifest（dependencies/pins 照 mq2/kit+source_url/notes 含手册路径+原页+网盘链接+改造要点+非线性/预热/非精标限制）→ wordlist.json 补录（感知传感器：光敏电阻/雨滴/粉尘/紫外线，lib_modules 挂接）→ 测试（`test_module_<slug>.py` 照 test_module_mq2.py 模板——薄封装生成断言比照 test_module_mq2.py；test_pins.py 豁免元组按 mq2 方式对齐）→ 编译矩阵（复制 `run_joystick_matrix.py` 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified 回写 → 中文提交 → 工单 resolved → 逐件 code-review。

## 用户故事

1. 作为做题用户，我选中 `photoresistance`/`rain`/`gp2y1014au`/`s12sd` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + 服务函数读光照百分比/雨量百分比/粉尘浓度估算/UV 指数。
2. 作为做题用户，我做光控灯/自动调光、雨感雨刷/晾衣架、粉尘报警/空气净化联动、紫外线监测（户外运动/防晒提示）时，不用再读器件手册、不用自写 ADC 读取时序。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/编译记录/与库内同侪分工），可溯源到手册。

## 实现决策

### 既定事实（勿重新调研，批次 1-8 已实证）

① ADC12_0 **八通道已满**（endAdd=7：MEM0=adc/us016/mq2 薄封装共读 / MEM1-2=joystick X/Y / MEM3=ir_distance / MEM4=mq135 / MEM5=mq5 / MEM6=flame（通道 7 PA22）/ MEM7=soil（通道 12 PA14）；地猛星板上 A1_* 组设备数据不可用）——**本批及以后 ADC 类一律薄封装共读 MEM0**（mq2/us016 先例：多件同选同读一物理通道、一次转换一次读、采样节奏按用途自协调，绑定换引脚 = 改写 adcPin*.$assign + adcMem*chansel，模块零改动）；② SysConfig 拒绝同一 UART 外设多实例——本批无 UART 件；③ 地猛星 2×20 排针 31 个 IO 全被默认布局占用——新模块默认脚按「同选概率最低者与既有默认重叠」，同选经引脚绑定消解；④ **PA0/PA1 不可作 GPIO 输入**（2026-09-06 SysConfig CLI 实证——GPIO 输出可配 PA0，ir_remote_tx 先例；本批 gp2y1014au LED 为 GPIO **输出**，见例外）；⑤ 母版 GPIO 中断全走 GROUP1 单向量且被 motor 编码器独占——本批全部轮询，不注册中断；⑥ 软 I2C/软 SPI/软 UART/忙等不占 TIMER 先例——本批 ADC 件无时序要求（个位 us 级 read 忙等在 adc 模块内），仅 gp2y1014au 用 delay 模块做 LED 脉冲时序（毫秒级整形至 adc 读窗口）——**dependencies = ["adc"]（+["delay"] 视实现：gp2y1014au 需要）**；⑦ 工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`；⑧ 页内符号异常/器件正确性缺漏→人工复核、修正并记 notes（ir_remote 反码、sgp30 CRC8、ags10 重试写反、soil 页面注释函数名残留先例）；⑨ 一致性快检脚本先例 `.scratch/wiki-modules-batch8/sweep_31_modules.py` → 本批后更新 35 件版。

### 共性（四件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 bsp，改造为 `xxx_init()` + 服务函数，去 main/printf，函数名规范化（去 `Get_illume_Percentage_value`/`get_raindrop_percentage_value`/`Read_dust_concentration`/`Get_Ultraviolet_Intensity` 菜市场命名按库风格重命名），全局状态收敛为模块内静态（gp2y1014au 滑动平均缓冲）。
- **ADC 轮询**：页面 `ADC12_0_INST_IRQHandler` + `gCheckADC` 标志位一律改经 adc 模块 API 轮询（共享实例 IRQHandler 强符号唯一——mq2/flame/soil 先例）；`xxx_init` = `adc_init(ADC_1, ADC_Channel_0)`（使能转换，外设配置由 SYSCFG_DL_init() 完成）。
- **换算**：百分比/系数换算按页面原式；页面多采样累加（30 次/10 次/3 次×100ms）改 **5 次快平均**（us016 快平均先例，页面带长延时的采样循环不为速度妥协——快平均即逐次 adc_get 累加无内部延时）。
- **页面 DO（LM393 阈值比较）宏未用不声明**（photoresistance `Get_DO_In`/`GET_DO_IN`、rain `get_raindrop_do_value`/`GET_DO`——页面 main 演示均未用；gp2y1014au/s12sd 页面本无 DO）——骨架用 adc 原始值自行判断阈值即可，notes 写明；需要 DO 阈值直接判断时经引脚绑定 GPIO 输入自读。
- **默认脚 = PA24**（ADC12_0 MEM0 槽位，无新 `$assign` 行，manifest 按 mq2 声明方式对齐：角色 id `*_AO_CH0`、type adc、default PA24、required true）；四件 ADC 角色 `_CH0` 尾命名（us016 先例：`_CH<N>` 推导 MEM 索引——本批全 0 = MEM0 共读）。
- **wordlist**：感知传感器组补录四件（名称 + `lib_modules` 挂接），models 加词条。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `photoresistance` | sensor--photoresistance-sensor.md | ADC 模拟量薄封装（AO 输出，阻值随光强变化、分压出电压） | **无新实例**——依赖 adc 模块共享 ADC12_0 MEM0 槽位（mq2/us016 先例） | `dependencies: ["adc"]`；API = `photoresistance_init`（adc_init(ADC_1, ADC_Channel_0)）+ `photoresistance_read_percent`（float 出 0-100% 亮度百分比——页面 Get_illume_Percentage_value 原式 `(1 − value/4095)×100` **反向映射**：页面备注「最亮 100 最暗 0」自洽——光越强光敏电阻阻值越小（5516：光暗 ~1MΩ、光亮 8-20KΩ）→ 分压 ADC 值越小 → 百分比越高；5 次快平均（页面 Get_Adc_Value(10) 改）；页面 ADC 中断改轮询；页面 `Get_DO_In`/`GET_DO_IN`（LM393 阈值比较）未用不声明；notes 写明**与库内 bh1750（数字光照）分工**——光敏 = 廉价模拟件、非线性（阻值-照度对数非线性 + 分压输出非线性）、需标定，百分比仅相对强度（0=最暗 100=最亮），bh1750 = I2C 数字 lx 绝对量（1lx 分辨率）；页面工作电流「1MA」按 1mA 记；页面原脚 PA27 经绑定复现（绑 PA27 = 改写器 adcPin3→adcPin0 + adcMem0chansel→CHAN_0，mq2 notes 同口径） |
| `rain` | sensor--rain-sensor.md | ADC 模拟量薄封装（AO 输出 + DO 数字量可选） | 无新实例（同上） | `dependencies: ["adc"]`；API = `rain_init` + `rain_read_percent`（float 出 0-100% 雨量百分比——**页面公式方向修正**：页面正文「雨水越大，电阻值越小，模拟值转化为的数字值越大」但页面原式 `(1−value/4095)×100`（照原式雨越大百分比反而越低——与正文矛盾）→ 按「强度=水分覆盖=ADC 值关系」取证修正为**正向映射 `value/4095×100`**（雨越大百分比越高），notes 记录修正与依据（实物分压方向若相反改公式一处即可）；5 次快平均（页面 3 次 × 100ms 间隔改——页面 get_adc_value 内 delay_ms(20) 同步去除）；页面 ADC 中断改轮询；页面 `get_raindrop_do_value`/`GET_DO`（LM393 阈值比较）未用不声明；notes 写明**非线性/干净度影响**（雨滴板脏污/氧化/放置方式改变基线电阻——相对值非精标，「不同值对应降雨量多少毫米需实体测量」页面原话） |
| `gp2y1014au` | sensor--gp2y1014au-dust-sensor.md | ADC 模拟量 + **LED 驱动 GPIO 输出**（内置平均） | **无新 ADC 实例**（薄封装共读 MEM0）＋**新 GPIO 输出实例 `GP2Y1014`/LED**（例外——见下） | **薄封装例外（器件正确性缺漏，人工复核记 notes）**：GP2Y1014AU 红外 LED 必须由主控脉冲驱动（页面 Read_dust_concentration 按 clear→280us→采样→40us→set→9680us 的 10ms 周期），无 LED 脚传感器不工作 → 本件 = ADC 薄封装 + 1 × gpio_out（`dependencies: ["adc", "delay"]`；delay_us 走库内 delay 模块，忙等不占 TIMER）。API = `gp2y1014_init`（LED 空闲 = 关（引脚高）+ adc_init）+ `gp2y1014_read_dust`（float 出粉尘浓度**估算**——页面原式 `0.17×value − 0.1`，value = LED 亮窗口内 5 次快平均实测值 → 页面 Filter（10 点静态滑动平均）**内嵌为模块内静态环形缓冲**（页面滤波逻辑简单（10 值环形均值），照库依赖先例取舍：内嵌并记 notes，不依赖库内 filter 可选配套件）→ 换算出参）。页面 SAMPLES 30×2ms 改 5 次快平均（快平均在 280us 采样窗口内完成——页面「30 次 × 2ms 平均 ≈ 60ms」远超 10ms LED 周期，page 时序本就不自洽，改后单次读回到 ~0.3ms 级，notes 记录）；页面 Read_dust_concentration 时序按页面（clearPins = LED 亮、setPins = LED 关——页面极性原样）；**notes 写明粉尘浓度估算非精标**（页面公式对演示值/ADC 量程的标定不明确——0.17×4095−0.1 ≈ 696 超出常规 mg/m³ 量程：读数为相对参考值、烟/尘区分不能（红外漫反射原理对烟尘/水汽同样响应）、需标准粉尘标定）；页面无资料下载链接（仅移植成功案例） |
| `s12sd` | sensor--s12sd-uv-sensor.md | ADC 模拟量薄封装（SIG 放大电压输出，3 Pin） | 无新实例（同上） | `dependencies: ["adc"]`；API = `s12sd_init` + `s12sd_read_uv_index`（页面 Get_Ultraviolet_Intensity 换算原式——按 12bit ADC 值分档 0-11 级：<227→0、227-317→1、318-407→2、408-502→3、503-605→4、606-695→5、696-794→6、795-880→7、881-975→8、976-1078→9、1079-1169→10、≥1170→11（页面阈值表原式、0 低 11 高）；5 次快平均（页面 SAMPLES 30×5ms 改）；页面 ADC 中断改轮询；**notes 写明量程/波段**：检测波长 240-370nm（UV-A 波段——UV-B/UV-C 不响应）、测量角度 130°、温漂 0.08%/℃、工作 2.7-5V/1mA、板载 LM358 放大；等级表按页面标定（页面实测室内 0 级——户外强日光/遮挡/器件个体差异会偏移，防紫外提示场景按相对档位用）；页面 demo printf 删除 |

### 默认脚与重叠全景（2026-09-09 定稿）

四件默认 = **PA24（光敏/雨滴/粉尘 ADC、s12sd ADC，MEM0 槽位无新 `$assign` 行）+ PA1（gp2y1014au LED，新 GPIO 输出实例）**。

- ADC 角色四件共用 MEM0/PA24 槽位——**多件同选同读一物理通道**（mq2 先例 notes 口径：无共读冲突只意味同槽共读不互斥，物理上同一引脚同一 ADC 槽——与 adc/us016/mq2 同选默认即共读）；PA24 计数不变（仍 6：HUIDU L3 + UWB_UART RX + ADC12_0 adcPin3（adc/us016/mq2/本批四件薄封装共读）+ HC05_UART RX + NRF24L01 CSN + TCS34725 SDA）——**无新 $assign 行**，test_pin_bindings 刻意表 PA24 注释补本批四件。
- **gp2y1014au LED → PA1**：PA1 现状仅 1 个默认用户（I2C_0 sclPin = ml_mpu6050 硬 I2C SCL）——粉尘浓度监测与姿态采集（MPU6050）不同框、同选概率最低故叠此脚；**GPIO 输出可配 PA0/PA1**（2026-09-06 实证：仅 GPIO **输入**不可——PA0 作 GPIO 输出已实测过 CLI，ir_remote_tx 先例；PA1 同型，编译矩阵 CLI 实证兜底，若 CLI 拒绝改次选）；同选经引脚绑定消解；注意与 PA0 上 IR_TX 不同脚（粉尘监测与红外发射链无配对需求）；**刻意不叠**传感站标配（温湿度 PA7/PA28/PA31/PB6/PB7、光照 PA12/PA13、气体 PB18/PB20/PB24/PA18/PB9、显示 PB2/PB3）、报警（PA15 蜂鸣）、无线（PA8/PA9/PA22-26）、触摸（PA22/25/26/27）、运动（PA14/PB8/PB9/PA18/PB18/PB19/PB20）——粉尘监测站 = 显示 + 报警 + 温湿度 + 无线遥测常见组合，默认即不撞。
- 四件默认互不相撞（PA24 槽位唯一 + PA1 单独）——PA24 与批次 5 tcs34725 SDA / 无线族重叠系槽位唯一所致（mq2 同口径，同选经引脚绑定消解——tcs34725 SDA 或本批 ADC 件换脚即可）。
- 与既有默认重叠计数（更新 test_pin_bindings.py 刻意重叠表）：**PA1 1→2**（新条目：I2C_0 sclPin + GP2Y1014 LED）；PA24 计数不变（6——无新行，注释补本批四件共读）。

### 网盘依赖（本批无）

本批四件页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞：全部未上板（ADC 换算方向/UV 档位/LED 脉冲时序真机验证留后续）。

## 测试决策

照批次 1-8 先例逐件：

- `tests/test_pins.py`：
  - `test_module_code_has_no_pin_literals` 豁免元组 `("adc","us016","ir_distance","mq2","mq135","mq5","flame","soil")` 增 `"photoresistance","rain","gp2y1014au","s12sd"`（ADC_Channel_N 为 API 对偶枚举）；
  - `MSPM0_DEFAULT_MAP` 增 1 条（gp2y1014au `GP2Y1014_LED` → (`GP2Y1014`, "LED")——GPIO 组角色；四件 adc 角色无 GPIO 组/外设字段落点，由 test_pin_bindings 落点唯一性覆盖——mq2 先例）。
- `tests/test_pin_bindings.py` 刻意重叠表更新（PA1 新增 `"PA1": 2`（I2C_0 sclPin + GP2Y1014 LED——粉尘与姿态不同框、同选概率最低；GPIO 输出可配 PA1），PA24 注释补本批四件薄封装共读——计数不变 6）。
- `tests/test_syscfg_prune.py` 增 ADC12_0 新消费方断言（photoresistance/rain/gp2y1014au/s12sd 单选保留 ADC12_0；hc05 单选裁掉）+ GP2Y1014 实例断言（gp2y1014au 保留 / hc05 裁掉）。
- 新增 `tests/test_module_photoresistance.py` / `test_module_rain.py` / `test_module_gp2y1014au.py` / `test_module_s12sd.py`（照 test_module_mq2.py 模板）：manifest 结构（仅 mspm0 + 依赖 + 单/双角色 + notes 关键子串）+ mspm0 单选生成（syscfg 裁剪保留 ADC12_0 + gp2y1014au 含 `const GP2Y1014`、无其它 GPIO 实例、模块文件落盘、依赖 adc/delay 文件落盘、main.c 调 init/服务函数过静态门禁）+ 公式守卫：
  - photoresistance：`1.0f - ` 反向映射守卫、4095/100.0f、`ADC_Channel_0`、无 `ADC12_0_INST_IRQHandler`/`gCheckADC`；
  - rain：**正向映射守卫**（`/ (float)RAIN_ADC_MAX` 出现 + `1.0f - ` 不得在 percent 公式中——页面逆式回潮守卫）、4095/100.0f、`ADC_Channel_0`、无 IRQHandler；
  - gp2y1014au：`0.17f`/`0.1f` 系数守卫、`280u`/`40u`/`9680u` 时序常量守卫、滑动平均窗口守卫（`GP2Y1014_FILTER_WINDOW` 10）、`delay_us` 调用守卫（依赖 delay）、`ADC_Channel_0`、无 IRQHandler；
  - s12sd：阈值表守卫（`227u`/`318u`/`1170u` 等档位、0-11 级）、`ADC_Channel_0`、无 IRQHandler、notes 含「UV-A」「240-370nm」。
- 编译级验收：复制 `run_joystick_matrix.py` 改 slug（四件各一，放 .scratch/wiki-modules-batch9/：**gp2y1014au 单选生成含 GPIO 实例 → PA1 过 SysConfig CLI**——若 CLI 拒绝 PA1 则按③决策改次选脚并同步 spec/测试），gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- stm32 平台条目、上板真机验证（真机留后续，notes 注明）、新 ADC 通道/实例（**本批及以后 ADC 类一律薄封装共读 MEM0**——MEM 槽位 8/8 已满，另立决策已入 CONTEXT；gp2y1014au 的 LED GPIO 输出实例为器件必需例外）。
- 正文内嵌段落（行拆散版）不作为提炼源。
- 光敏/雨滴 DO 数字量阈值读取（LM393 阈值由模块可调电阻控制，页面 DO 函数未用于演示——同 mq2 策略不声明，需要时经引脚绑定 GPIO 输入自读；骨架用 adc 原始值自行判断阈值）。
- 光敏电阻照度绝对标定（lx 级）、雨滴「降雨量毫米」换算（页面原话「需实体测量」）、粉尘 ppm/mg/m³ 绝对标定（页面公式相对参考）、UV 档位跨器件标定——均记 notes 不落码。
- GP2Y1014AU 无 LED 引脚断开供电的检测、无烟/尘区分（红外漫反射原理）——notes 说明。
- 后续批次地图（另立工单）：10 = 杂项收尾（ms1100 气体（薄封装）、l298n（motor 同族）、jy61p（软 I2C 六轴）、open-mv4（软/UART 帧解析）、sht20（软 I2C）、mq-3/4/6/7/8/9 同构快补）；11 = 彩屏线（需网盘厂家例程后开工——链接在 sources/materials/lckfb-地猛星移植手册/网盘索引.md）。

## 补充说明

- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 2026-09-09 复跑：真缺 12 篇（nrf24l01、8 篇彩屏、1.3 单色、mpu6050）——本批四件均在全自洽 58 篇内。
- 工单：`issues/01-module-photoresistance.md` → 02 rain → 03 gp2y1014au → 04 s12sd（互相独立、无共享 ADC 演进（薄封装无 syscfg 改动）；实施按简→繁：photoresistance → rain（含方向修正取证）→ s12sd → gp2y1014au（唯一带 GPIO 实例/delay 依赖/滤波内嵌件））。
- 完成后：全量测试套件 + 批次 1-9 全部 35 件一致性快检（`.scratch/wiki-modules-batch9/sweep_35_modules.py`）+ 批次 1-9 全部 35 件 code-review 收尾 + CONTEXT.md 平台行补录四件（薄封装共读 MEM0 决策 + gp2y1014au LED 例外）+ 中文提交（.githooks/commit-msg 强制中文；无新增 .ps1）。
- 词表预算（2026-09-09 实测定稿）：四件入库后默认词表完整 wire（json.dumps ensure_ascii 口径，budget.wire_size）实测 **6341**（> 5934 fit 上限 6100−166——尾部类别被截、方案名丢失，test_wordlist_segment 契约红证）→ 按批 5/6/7/8 先例上调 WORDLIST_PROMPT_BYTES **6100→6600**（fit 上限 6434 ≥ 6341 全量送达 + 93B 余量），词表段全量 6341 比旧截断形态 6100 多 241B → REFERENCE_FULLTEXT_BYTES **61500→61000** 保 2KB 边界余量（预判口径「+400B」与实际 +441B 同向）。

## 实施结论（2026-09-09，收尾补记）

- 四件编译矩阵全部 PASS（0 error/0 warning）：photoresistance、rain、gp2y1014au（**GP2Y1014/LED = PA1 经 SysConfig CLI 实证据合法**——2026-09-06 实证的「PA0/PA1 仅 GPIO 输入不可」延伸确认）、s12sd；verified=true 全部回写；未上板（notes 注明）。
- rain 公式方向定稿为**正向映射**（正文取证修正，实现 + 守卫 + notes 三处一致）；photoresistance 反向映射与页面「最亮 100 最暗 0」自洽。
- gp2y1014au 的 LED GPIO 实例定稿为默认 PA1（同选概率最低：仅与 I2C_0 SCL 重叠——粉尘与姿态不同框；i2c_bus_share 测试按 ir_distance/ttp224 绑走先例恢复纯 I2C 共享组）。
- 35 件一致性快检（sweep_35_modules.py）全 OK；词表预算/账目注释随本 spec 同步（llm.py/budget.py 记账链）。
- 工单 01-04 全部实施完毕（状态待收尾标记 resolved）。

## code-review 结果（2026-09-09，双轴并行评审，固定点 55cad1dc）

- **标准轴**：3 项硬违规（① gp2y1014au verified 提交态 false——已随收尾提交转 true；② 词表预算未随提交上调——已随收尾提交 6100→6600/61500→61000；③ 工单未收尾——已标记 resolved）+ 2 项判断（s12sd `S12SD_UV_INDEX_MAX`、gp2y1014au `GP2Y1014_ADC_MAX` 死常量——已移除并同步守卫断言）；其余合规项（ADR 0009/简介判据/零引脚字面量/薄封装先例/syscfg 风格/中文规范）全部通过。
- **规格轴**：实现与 spec/工单逐条一致、未发现实现错误；差异项均为未提交收尾项（同标准轴 ①②③，工作区已修正）；范围外提示（010c3df7 系批次 8 收尾修正、i2c_bus_share 绑走用例为保持既有测试绿的必要适应（照 ir_distance/ttp224 先例）、gp2y1014au notes 增补规格/分工）均认可保留；弱观察（40u 时序仅 header 守卫）已补强为调用点断言。
