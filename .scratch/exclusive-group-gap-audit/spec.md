# spec — 全库排查「同类功能件没有同组」（功能组缺口补齐）

**状态：** 已拍板（2026-09-13；范围 = 高置信度四组并组，无线族三条列「待用户拍板」不动手）。

## 问题陈述

用户在推荐结果里看到「已经选了姿态传感器 `imu_uart`，句子 12 又冒出一个同类件 `jy61p`」。
根因不是界面：`exclusive_group` 是**模块级 manifest 声明**——没声明的模块

1. 不属任何功能组 ⇒ 需求句里走「可移除 chip」而不是组卡单选框；
2. 同组互斥收敛（`selection.converge_exclusive_group_selection`）看不见它
   ⇒ **同一功能的两件会同时进工程集**，用户莫名其妙多配一个件。

`jy61p` 那一例已由 `.scratch/attitude-group-jy61p/01` 修掉。但库内 93 个模块里只有 8 个
在组内（3 个组）——**同一形状的洞还在别处**：库内自己的 notes 早就写着「互替件」「显示族
互替」「同址不可同挂」「互替同脚」，而这些件一件都没进组，同功能重复件照样同时进工程集。

## 方案

对全库做一次机械筛 + 逐条取证，把**证据充分**的同功能件并进功能组；证据不足或组语义有
歧义的条目**不动手**，列成清单交给用户拍板（不自己拍板有歧义的组语义）。

机械筛三道（脚本 `.scratch/exclusive-group-gap-audit/scan.py`）：

- **A 关键词筛**：`description` + `platforms[*].notes` 里出现**别的模块 slug**且带
  「互替/替代/可替代/等效/同款/承接/二选一/同功能」一类词（噪声高，逐条判）。
- **B 默认脚重叠筛**：同平台两模块 `pins[].default` 落到同一脚（母版刻意的「同选概率最低者
  重叠」设计，**只作候选池**，语义不同框者一律不并）。
- **C 器件族/同实现形态筛**：同一器件不同接口（UART/I2C/SPI）、同型号不同屏、同物理量不同器件。

判据（真判据，比关键词硬）：**默认脚重叠 ∪ 库内文字自证「互替」，且"语义上不会同时选"**
（姿态×姿态、测距×测距、显示×显示、气压×气压、声提示×声提示……）。

**本轮动手并组（6 组）**：

| 组 id | label | 成员 |
|---|---|---|
| `distance` | 距离测量 / 测距传感器 | us016 / ir_distance / vl53l0x / sr04 |
| `display` | 显示 / 屏幕 | lcd / oled / max7219 / ili9341 / ili9488 / st7789_para |
| `barometer` | 气压 / 海拔传感器 | bmp180 / ms5611 |
| `sound-prompt` | 提示输出 / 声 | beep / jq8900 |
| `zigbee-rx`（扩容 + 改中性组名，id 不变） | 无线链路 / 数传 | as32 / ec01g / esp01s / hc05 / nrf24l01 / zigbee_link / zigbee_uart |
| `positioning`（新开） | 定位 / 位置测量 | uwb_uart / neo_6m |

**无线族（第二批，用户拍板 2026-09-13「全部按你建议」→ 按复核后的建议）**：并入 `zigbee-rx`
并把 label 从「Zigbee 无线链路（接收侧）」改成中性名「无线链路 / 数传」——组 id 保持不变
（id 不是用户可见词，改名会牵动赛题 `hint_module_groups` 存量值）；复核推翻首轮两处口径
（`ec01g`、`hc05`/`esp01s` 从「不并」改为「并」），理由见排查表 §2.2。
**不并**：语音两件（`jq8900`×`syn6288`，库内自证「常同选」）、温湿度族（`aht10`/`sht20`/
`sht30`/`dht11`，库内自证「同选互不冲突」+ 默认脚刻意错开）。

**判定为「不并」并留证的（防下一轮重复产出同一批候选）**：灰度/姿态/zigbee 三组已是先例；
温湿度互替件（aht10/sht20/sht30、dht11）、气体阵列（mq 系 8 件）、光照/颜色（bh1750/tcs34725/
s12sd/photoresistance）、单总线温湿度×温湿度、语音两件（jq8900×syn6288）、led/beep/led_beep、
显示族×LED 板载灯、`zigbee_uart_key`（发送侧成对件）、内部件/协议切片——逐条理由见排查表
`.scratch/exclusive-group-gap-audit/audit.md`。

## 用户故事

1. 作为**参赛选手**，我想要「同一功能的两件不会同时进工程集」，以便不会莫名多配一个件。
2. 作为**参赛选手**，我想要需求句里出现的同类件变成组卡上的可选项（radio + role），以便
   我一眼看出「这两个是一件东西的两种买法」。
3. 作为**参赛选手**，我想要组卡上的 role 说清「选它差在哪」，以便不用去翻手册。
4. 作为**维护者**，我想要每条并组都有代码/引脚/库内文字证据，以便不靠感觉分组。
5. 作为**维护者**，我想要「不并」的判定也留一句为什么，以便下一轮盘点不重复产出同一批候选。
6. 作为**维护者**，我想要红证/绿证用同一份载荷跑生产解析层，以便「修好了」不是自说自话。

## 实现决策

- **只动 `library/modules/<slug>/manifest.json` 的 `exclusive_group`**，不顺手改别的字段。
- 组声明形状沿用既有：`{id, label, role}`；同 id 的 label 必须**逐字一致**
  （`manifest.collect_exclusive_groups` 不一致即抛 `ManifestError` 大声失败）；每个成员
  的 `role` 必写，且写「选它差在哪」（接口/精度/形态/配套）。
- 组名依据：既有三组的命名形态 = 「功能名（中文）/ 硬件类别」——`8 路灰度传感器驱动`、
  `航向保持 / 姿态传感器`、`Zigbee 无线链路（接收侧）`。新组名照此：功能名在前、斜杠后
  写硬件/接口类别，**不写具体型号、不写代码符号**。
- 平台投影：`scope_group_members` 只留该平台有条目的成员；某平台投影后 <2 成员 = 不出卡
  （本四组双平台成员都 ≥2）。`beep` 的 mspm0 条目是占位实现（`pins` 空）但**有条目**，
  故 mspm0 侧 `sound-prompt` 仍是 2 成员，出卡与硬拦不变；真正要处理的现场
  （`[0]` stm32 语音/蜂鸣公告）在 stm32 侧。
- **不加 `HARD_EXCLUSIVE_PAIRS`**：那是「同选必然重复定义中断符号」的生成侧硬兜底
  （zigbee 那条），本四组同选不必然编译失败，属软单选语义。
- **不动** `coverge_exclusive_group_selection` 的「保模型清单首个」规则，也不动前端。

## 测试决策

- 真库基准：`tests/test_module_universality.py::test_exclusive_groups_aggregate_on_the_real_library`
  （组 id 集合、每组 label 与成员清单逐字断言）——加成员必改，改的是**基准值**不是判据。
- 跨模块结构用例：新四组各自的「同组 + label 逐字 + role 齐备」用例，照
  `tests/test_module_jy61p.py::test_jy61p_declares_attitude_hold_group_with_imu_uart` 先例。
- 红证/绿证（真载荷、零额度）：`.scratch/exclusive-group-gap-audit/probe-group-convergence.py`
  ——同一份「同一题同时推这两件」的需求层，跑真实 `selection.build_module_selection`：
  红 = 两件同时在顶层 `modules`；绿 = 只剩一件、另一件进 `dropped_exclusive_members`。
  脚本内置一条**对照样例**（已修好的姿态组，必须绿）——否则「全绿」可能是探针没接上收敛链路。
- 端到端 fixture：`.scratch/group-choice-required/make-payload.py` 重跑，看打印的组卡里
  `recommended` 每组 ≤1（有重复即还有漏组）。
- 全量回归：`pytest -q` + `node --test tests/js/*.test.mjs` + `mypy src/contest_generator/selection.py`。

## 范围外

- **不**改 AI 提示词与收敛规则（谁被标为 `recommended` 照旧）。
- **不**动引脚默认值、不动 `pin_config.h` / `mspm0.syscfg`（本轮只补组声明）。
- **不**改 `zigbee-rx` 的组 id（只改 label → 用户可见词；id 改名会牵动赛题
  `hint_module_groups` 存量值与多处夹具，需另立迁移单）。
- **不**把「同一物理量、不同器件」一律并组（温湿度族、气体阵列各有独立价值，见排查表）。
- **不**扩 `HARD_EXCLUSIVE_PAIRS`（生成侧硬兜底不是本轮的活）。

## 补充说明

- 「默认脚重叠」是母版**刻意**的设计（同选概率最低者重叠，同选经引脚绑定消解），所以它
  只是候选池的入口，**判据是语义**：同一功能不会同时选两件才是真候选。
- 「刻意错开默认脚」的注释反而是**不同框**信号（`jq8900` × `syn6288`：语音两件常同选、
  默认即不撞）——这类**不并**。
- **判据一致性**（复核第二轮修掉的漏洞）：同一类理由必须同判——「同一路 UART 只能挂一个
  驱动」对 LoRa/Zigbee/NB-IoT/蓝牙/WiFi 一视同仁，不能只并其中一半（见排查表 §2.2
  「改主意原因」列）。共存需求由**组卡候选 + 用户点选**承担，不会静默丢件。

## 拍板记录（2026-09-13，用户「全部按你建议」）

| # | 候选 | 最终决定 |
|---|---|---|
| 1 | `as32`（LoRa）× `zigbee_link`/`zigbee_uart` | **并入 `zigbee-rx` + 组名改「无线链路 / 数传」**（连 `nrf24l01`、`ec01g`；证据：默认脚完全相同 + notes 明写「互替件」「二选一接入」） |
| 2 | `uwb_uart` × `neo_6m` | **新开 `positioning`「定位 / 位置测量」**（mspm0 侧单成员 → 该平台不出卡，属预期） |
| 3 | `hc05` × `esp01s` | **并入 `zigbee-rx`**（复核推翻首轮「不并」：同一路 UART_1、notes 明写「互替件同脚先例」，与 LoRa 同口径） |
| 4 | `ec01g`（NB-IoT）× zigbee/LoRa | **并入 `zigbee-rx`**（复核推翻首轮「不并」：同上，notes 明写「互替件同脚先例（无线链路二选一接入）」） |
| 5 | `jq8900` × `syn6288`（语音两件） | **不并**（notes 自证「常同选」= 不同框） |
| 6 | 温湿度族（`aht10`/`sht20`/`sht30`/`dht11`） | **不并**（notes 自证「同选互不冲突」+ 默认脚刻意错开） |

