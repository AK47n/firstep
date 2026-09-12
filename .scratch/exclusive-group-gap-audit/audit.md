# 全库排查表 —「同类功能件没有同组」（2026-09-13）

**任务**：用户现场是「已经选了姿态传感器 `imu_uart`，句子 12 又冒出一个同类件 `jy61p`」；
根因 = `exclusive_group` 是**模块级 manifest 声明**——没声明的模块既不进组卡、也不吃同组互斥
收敛（`selection.converge_exclusive_group_selection`），同一功能的两件会**同时进工程集**。
本表 = 按同一形状全库排查的取证与逐条裁定。

配套文件：

| 文件 | 内容 |
|---|---|
| `scan.py` / `scan-output.txt` | 阶段一机械筛（三道筛 + 全量输出） |
| `dump.py` / `dump-*.txt` | 候选模块的 description / notes / 默认脚全文取证（只读） |
| `probe-group-convergence.py` | 红证/绿证探针（真库 + 生产解析层，零额度） |
| `red-before.txt` | **改前**跑出来的现场（7/8 红：同功能两件同进顶层 modules） |
| `green-after.txt` | **改后**同一批载荷（4 组绿、3 条待拍板仍红） |

## 一、机械筛（阶段一）

复跑命令（全部只读、零额度）：

```powershell
$env:PYTHONIOENCODING='utf-8'; python .scratch/exclusive-group-gap-audit/scan.py
$env:PYTHONIOENCODING='utf-8'; python .scratch/exclusive-group-gap-audit/dump.py <slug> [...]
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; python .scratch/exclusive-group-gap-audit/probe-group-convergence.py
```

- **筛 A（关键词）**：`description` + `platforms[*].notes` 里提到**别的模块 slug** 且带
  「互替/替代/可替代/等效/同款/承接/二选一/同功能」——命中 **104 条**，噪声主要来自
  「引脚避让说明」（`key_matrix` 提 `ttp224`、`nrf24l01` 提 `as32`）与「器件换代说明」
  （`bmp180` 提「BME280/BMP280 换代替代品」）。逐条判，见第三节。
- **筛 B（默认脚重叠）**：同平台两模块 `pins[].default` 落到同一脚——
  stm32 侧 27 个脚、mspm0 侧 28 个脚有 ≥2 个模块角色（全量清单见 `scan-output.txt`）。
  母版是**刻意**让「同选概率最低者重叠」的（`pin_config.h:4-16` 抬头注释、
  `tests/test_mspm0_default_layout.py` 白名单），所以这一筛只作**候选池入口**，判据是语义。
- **筛 C（同功能多实现形态）**：同一器件不同接口（UART/I2C/SPI）、同型号不同屏、
  同物理量不同器件——人工归族清单见 `scan-output.txt` §C。
- **筛 D（kit 交叉提及）**：命中 1 条（`led` 的 mspm0 notes 提 MPU6050），无关。

**真判据**：`默认脚重叠 ∪ 库内文字自证「互替」` **且**「语义上不会同时选」。
反例口径（**不并**）见第三节末。

## 二、逐条裁定（阶段二）

### 2.1 并组（4 组 / 13 个模块）——已实施

红证口径：同一份「同一题同时推这两件」的需求层载荷，跑真实
`selection.build_module_selection`（真库 manifest + 真摘要），看是否两件都进顶层 `modules`。
改前 `red-before.txt`（红计数 7/8；对照样例 = 已修好的姿态组必须绿），改后 `green-after.txt`。

#### 组 1 `display`「显示 / 屏幕」（6 件）

| 项 | 内容 |
|---|---|
| 成员 | `lcd` / `oled` / `max7219` / `ili9341` / `ili9488` / `st7789_para` |
| 证据 1 | `lcd` stm32 notes：「与 oled SPI 五脚组（PB4-7/PA5 子集）/**max7219 三脚组（PC13-15）显示族互替同脚**（一次选一块屏——大屏/小屏/数码管互替，互替同脚先例）」 |
| 证据 2 | `max7219` stm32 notes：「与 lcd 六脚组（PB4-7/PA5/PA15）/oled SPI 五脚组**显示族互替同脚**（一次选一块屏……）」 |
| 证据 3 | `ili9341` / `ili9488` description：「默认脚 = lcd 六脚组同款（ILI 屏×中景园屏互替同脚）」 |
| 证据 4 | `st7789_para` description：「与显示族（lcd/oled SPI/max7219/ili 系）互替——一次只选一块屏」 |
| 证据 5 | `lcd` mspm0 notes 反向自证：「**刻意不叠显示族**（oled PB2/PB3、max7219 PB9/PA18/PB18、ws2812 PA14、led PA15）与环境站」 |
| 默认脚位置 | `pin_config.h:588-603`（max7219 DIN/CLK/CS=PC13/14/15）、`:605-627`（lcd 六脚 PB4/PB5/PA5/PB6/PB7/PA15）、`:649-664`（oled SPI 五脚 PB4-7/PA5）、`:666-687`（ili9341 同款六脚）、`:689-711`（ili9488 同款六脚）、`:713-755`（st7789 14 脚含 PC13-15）；mspm0 侧实例名 `LCD`/`OLED_SPI`/`MAX7219`/`ILI9341_*`（仅 stm32 条目）/`ST7789_PARA_*`（仅 stm32 条目） |
| 判定 | **并组**——「一次选一块屏」是库内反复写死的设计口径 |
| 红证 | 改前：载荷「彩屏显示实时数据与界面菜单」+「数码管显示比赛计时与得分」→ 顶层 `['lcd', 'max7219']` |
| 绿证 | 改后：顶层 `['lcd']`、`dropped = {'display': ('max7219',)}` |
| 反例说明 | `lcd` 六屏合一是**同一模块内**的变体、`oled` I2C/SPI 两变体同模块——**不拆模块**（拆了反而制造「同类件」）；本组治的是「多块不同的屏会同时进工程集」 |

#### 组 2 `distance`「距离测量 / 测距传感器」（4 件）

| 项 | 内容 |
|---|---|
| 成员 | `us016` / `ir_distance` / `vl53l0x` / `sr04` |
| 证据 1 | `us016` stm32 notes：「**与 ir_distance 互替件同脚**（两测距件同一物理脚只能接一件——互替同脚先例语义：二选一接入无需另消解）」 |
| 证据 2 | `ir_distance` description + stm32 notes 同句反向自证（「与 us016 互替件同脚」） |
| 证据 3 | `vl53l0x` notes：「库内无 ToF 激光测距模块——**现有测距 = 超声波（us016/sr04）+ 红外（ir_distance）**+ 定位 UWB/GPS」= 库自己把四件归成一个「测距」族 |
| 证据 4 | `sr04` description 与 `us016` 同为超声波测距（TRIG/ECHO 接口 vs 模拟量 AO = 同一器件不同接口形态） |
| 默认脚位置 | `pin_config.h:196-204`：`US016_AO_CH` 与 `IR_DISTANCE_AO_CH` **同为 `ADC_Channel_5` = PA5**（互替同脚）；mspm0 侧不撞（`us016` ADC12_0 MEM0 = PA24，`ir_distance` MEM3 = PA27，`sr04` PB24/PB8） |
| 判定 | **并组**——同一题不会同时选两个测距件（同一路距离量） |
| 红证 | 改前：「测量车前障碍物距离并避障（超声波）」+「非接触测距判断落点（红外）」→ 顶层 `['us016', 'ir_distance']` |
| 绿证 | 改后：顶层 `['us016']`、`dropped = {'distance': ('ir_distance',)}` |
| 已知留白 | `vl53l0x` 仅 stm32 条目、`sr04` 仅 mspm0 条目——平台投影后两组各 4/3 成员，都出卡 |

#### 组 3 `barometer`「气压 / 海拔传感器」（2 件）

| 项 | 内容 |
|---|---|
| 成员 | `bmp180` / `ms5611` |
| 证据 1 | `bmp180` stm32 notes：「**与 ms5611 同址 0xEE → 两件互替不可同挂**——同一总线同址双选必冲突：默认脚各取一挂 PA6/PA7、选一只，同选经引脚绑定换独立总线或换件」 |
| 证据 2 | `ms5611` stm32 notes 同句反向自证 + notes「两件互替、默认脚错开（PA28/PA31 × PA23/PA24）、同选无冲突」 |
| 证据 3 | 两件 description 共用同一个 44330 海拔公式、同一个 `read_altitude` 出参——同一物理量、同一个功能的两种硬件 |
| 默认脚位置 | `pin_config.h:350-357`（两件 stm32 默认 SCL=PA6/SDA=PA7，**同址 0xEE**）；mspm0 侧 `BMP180` 实例 PA23/PA24 × `MS5611` 实例 PA28/PA31（刻意错开） |
| 判定 | **并组**——stm32 侧同址是**硬冲突**，且语义上「一块板只要一个气压计」 |
| 红证 | 改前：「气压海拔检测与爬楼计层」+「无人机定高闭环需要高精度气压计」→ 顶层 `['bmp180', 'ms5611']` |
| 绿证 | 改后：顶层 `['bmp180']`、`dropped = {'barometer': ('ms5611',)}` |

#### 组 4 `sound-prompt`「提示输出 / 声」（2 件）

| 项 | 内容 |
|---|---|
| 成员 | `beep` / `jq8900` |
| 证据 1 | `jq8900` description：「mspm0 默认 PB19、stm32 默认 PA15（**与蜂鸣器提示输出互替**）」 |
| 证据 2 | `jq8900` stm32 notes：「OUT=PA15（与蜂鸣器 BUZZER 同脚：语音播报与蜂鸣器为**提示输出互替**（替代而非组合）、同选概率最低）」 |
| 证据 3 | 两件 stm32 默认脚相同：`pin_config.h:102-103` `BUZZER_PIN = Pin_15`（PA15）、`pin_config.h:497-498` `JQ8900_PIN = Pin_15` |
| 判定 | **并组**——都是「用一声/一句提示用户」的输出件，题面「声光提示」一个槽位只需一个 |
| 红证 | 改前：「到点蜂鸣器提示报警」+「语音播报比赛成绩」→ 顶层 `['beep', 'jq8900']` |
| 绿证 | 改后：顶层 `['beep']`、`dropped = {'sound-prompt': ('jq8900',)}` |
| 已知留白 | `beep` 的 mspm0 条目是占位实现（`pins` 空）但**有条目**，故 mspm0 侧仍 2 成员、出卡与硬拦不变 |

### 2.2 待用户拍板（3 条 + 3 条备选，**未动手**）

| # | 候选 | 证据 | 现状（改后仍红） | 我的建议 |
|---|---|---|---|---|
| 1 | `as32`（LoRa）× `zigbee_link`/`zigbee_uart` | `as32` mspm0 notes：「默认挂 UART3（ZIGBEE_UART 宿主——**LoRa 与 Zigbee 无线数传互替件**、同选概率最低）」「as32×zigbee_uart/zigbee_link 同选 = UART3 双实例 CLI 拒绝」；stm32 notes 同款；默认脚完全相同（`pin_config.h:394-399` `AS32_UART = UART_3` TX=PB10/RX=PB11 = `pin_config.h:380-386` ZIGBEE_UART 原脚；mspm0 `AS32_UART` PA26/PA25 = `ZIGBEE_UART` 实例原脚） | 顶层 `['as32', 'zigbee_link']` | **并入并把组名改成中性名**（如「无线串口链路（透传）」）：三件都走同一路 UART 透传、同一物理链路只能一个消费者；**若你要求保留现组名 `zigbee-rx`，则本条不并**——把 LoRa 挂在「Zigbee 无线链路（接收侧）」名下语义是错的 |
| 2 | `uwb_uart` × `neo_6m` | `neo_6m` description「默认 UART_1（与 UWB 定位互替同脚）」+ notes「与 UWB 定位链路**互替件同脚先例**（GPS 室外定位 × UWB 室内定位……）」；默认脚完全相同（stm32 PA9/PA10 `pin_config.h:372-378` UWB × `:531-536` NEO_6M；mspm0 `UWB_UART` PA23/PA24，`neo_6m` 无 mspm0 条目） | 顶层 `['uwb_uart', 'neo_6m']` | **新开组**「定位 / 位置测量」：mspm0 侧投影后只剩 UWB 单成员 → 该平台不出卡（合理：该平台只有一件）；组名只能按「功能」而非「协议」（跨厂商跨原理） |
| 3 | `hc05` × `esp01s` | `esp01s` stm32 notes：「默认 UART_1 = UWB_UART 宿主（ESP-01S 手机/上位机遥控 × HC05 蓝牙 = 同手机遥控链路**互替件同脚先例**、同选概率最低）」；`hc05` notes 反向自证；默认脚相同（`pin_config.h:411-416` × `:545-550`） | 顶层 `['hc05', 'esp01s']` | **不并**：蓝牙近场配置链路 vs WiFi 联网上报能力不同框（可共存）；只在「手机遥控」单一口径下才是互替——**口径由你定** |
| 4（备选） | `ec01g`（NB-IoT）× zigbee/LoRa | `ec01g` stm32 notes：「NB-IoT 蜂窝无线 × Zigbee/LoRa 无线链路**互替件同脚先例**（无线链路二选一接入）」；默认 UART_3 = PB10/PB11 同脚（`pin_config.h:561-566`） | 顶层 `['as32'/'zigbee_*', 'ec01g']`（未单测，同上形状） | **不并**：蜂窝联网（远程遥测/云端上报）与短距透传不同框；且 `ec01g` 自带 GPS（与候选 2 的语义重叠） |
| 5（备选） | `jq8900` × `syn6288`（语音两件） | 两件都是软 UART TX 语音件；但 `jq8900`/`syn6288` notes 都写「**语音两件常同选，默认即不撞**」（刻意错开 PB19 × PB20 / PA15 × PC14） | 顶层 `['jq8900', 'syn6288']` | **不并**：曲目播报（预存语音）vs 文本合成（任意文本）能力有真实差异，与 `led`/`beep` 并列可共存同口径 |
| 6（备选） | 温湿度互替件（`aht10`/`sht20`/`sht30`/`dht11`） | 各件 notes 互称「温湿度互替」；但 `sht30` notes 明写「环境站按需任选，**同选互不冲突**（各自默认脚错开）」，`sht20` notes 写「**刻意不叠温湿度互替件** aht10 PB6/PB7、dht11 PB7、sht30 PA28/PA31、ds18b20 PA7」；stm32 侧六件软 I2C 默认共挂 PA6/PA7 是**合法共享**（地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异，白名单登记） | 顶层 `['sht30', 'aht10']`（未单测） | **不并**：库内文字自证可共存 + 默认脚刻意错开 = 不同框信号；若你认为「一块板只需一个温湿度件」，推翻此判定即可（改法 = 四件各加一组 `env-temp-humidity`） |

### 2.3 判定为「不并」并留证（37 条，防下一轮重复产出同一批候选）

**口径**：以下三类**不并组**——① 并列可共存（各有独立价值）；② 内部件/协议切片（不是器件）；
③ 母版**刻意错开**默认脚（= 设计者认定「常同选」，错开是不同框信号，不是同组信号）。

| # | 候选 | 为什么不并（证据） |
|---|---|---|
| 1 | `led` × `beep` × `led_beep` | 声光提示是并列可共存的三个件（用户明示的反例）；`led_beep` 是「声+光」复合件，本身就不是 `led` 的替代品 |
| 2 | `dht11` × `sht30` | 不同物理量/不同器件口径（用户明示的反例）；`sht30` notes「同选互不冲突」 |
| 3 | `aht10` × `sht20` × `sht30` × `dht11` | 见 2.2 #6：互称互替但 notes 自证可共存、默认脚刻意错开 |
| 4 | `ds18b20` × `mlx90614` | 接触式单总线测温 × 非接触红外测温，测量方式与场景不同（`sht20` notes 把 `mlx90614` 归为「不接触场景」） |
| 5 | `mq2`/`mq3`/`mq4`/`mq5`/`mq6`/`mq7`/`mq8`/`mq9`/`mq135`/`ms1100`/`ags10`/`sgp30` | 12 件测**不同气体/不同物理量**（烟雾、可燃、酒精、CO、甲烷、液化气、氢气、空气质量、CO₂/VOC 等效值），不是互替件；stm32 侧 16 个 ADC 角色共读 PA5 是**合法共读**（`pin_config.h:156-192` 注释 + ml_adc 顺序调用互不干扰）；`gp2y1014au` notes 明写「smoke 类与本件量纲不同**不可互替**」 |
| 6 | `bh1750` × `tcs34725` × `s12sd` × `photoresistance` | 光照强度（lux）× 颜色识别（RGB）× 紫外 × 光敏电阻——不同物理量；`tcs34725` notes 自证「颜色识别属视觉类，与 K230 视觉互替」（那是另一条语义，见 #7） |
| 7 | `tcs34725` × `k230`/`open_mv4`（视觉） | `tcs34725` notes 说「与 K230 视觉互替」——但 `k230`/`open_mv4` 是**协议切片/视觉链路件**（`k230` 是 python artifact + 帧解析、`coord_detect` 是帧协议切片，`open_mv4` 是串口帧件），不是「另一种颜色传感器」；且 `open_mv4` 仅 mspm0、`tcs34725` 双平台。**待你确认是否要开「视觉/颜色识别」组**——我建议不并（协议切片不属器件组） |
| 8 | `tcs34725` × `vl53l0x` | stm32 侧**同址 0x29 不可同挂**（`pin_config.h:568-587` 注释 + `vl53l0x` description），但两件是不同物理量（颜色 vs 距离）= 同址冲突 ≠ 同类；冲突由引脚绑定/换件消解，**不并组**（并组会把「颜色传感器」误标成测距件） |
| 9 | `vl53l0x` × `tcs34725` 的「同址」这一半 | 同上（硬冲突已在 notes 记录；`distance` 组只按「测距」语义收 `vl53l0x`） |
| 10 | `key` × `key_matrix` × `ttp224` × `ec11` | 独立按键 × 4×4 机械矩阵 × 4 路电容触摸 × 旋转编码器——人机输入的不同形态，可共存（键盘+旋钮+触摸同面板是常见组合）；`key_matrix`/`ttp224` 都写「**刻意不叠人机面板组合**（KEY/OLED/数码管——键盘+屏幕/按键同框）」= 不同框信号 |
| 11 | `ir_remote` × `ir_remote_tx` | 红外**接收**解码 × 红外**发射**编码——发/收常配对，`pin_config.h:472-487` 明写「与 ir_remote_tx 默认 PA9 刻意错开——发/收常配对、双选默认不撞」= 常同选 |
| 12 | `ir_remote` × `hc05`/`nrf24l01`/`joystick` | `ir_remote` notes 说「红外遥控与其它无线链路（Zigbee/2.4G）及手动摇杆**互为替代控制方案**」——但这是「控制方式」层面的泛化，四者物理形态/距离/场景完全不同（红外近场指向性 vs 蓝牙手机 vs 2.4G 点对点 vs 有线摇杆），题面「遥控」一个槽位确有歧义 → 若你要按「遥控输入」并组，需一次并 `ir_remote`/`hc05`/`esp01s`/`nrf24l01`/`joystick` 五件，**我建议不并**（跨层泛化会吃掉各自的独立价值） |
| 13 | `human_ir` × `microwave_radar` × `ir_beam` × `ttp224` | `human_ir`/`microwave_radar` notes 明写「**场景二选一或组合**（微波+人体红外双判据，页面推荐组合）」「默认脚互不相撞」= 常组合使用，不同框 |
| 14 | `flame` × `mq*`/`photoresistance` 等 ADC 薄封装 | 16 个 ADC 角色共读 PA5 是**合法共读**（`pin_config.h:156-167` 注释：ml_adc 每次先写 SQR3 选通道，顺序调用互不干扰）；「同一物理脚只能接一件器件」是接线事实、不是「同类功能」 |
| 15 | `motor` × `l298n` × `step_motor` × `servo` × `pca9685` | 驱动**不同的执行机构**（直流减速电机 / 大电流电机 / 步进 / 舵机 / 16 路舵机扩展）；`l298n` × `motor` 写「互替刻意错开 TIM 与脚（一辆车只接一种驱动）」——但 `motor` 是「TB6612 双电机 + 编码器闭环」件的整套驱动，`l298n` 是「大电流 PWM×2」，两者都给电机供电，语义上确实可能二选一 → **列为待确认**（我建议不并：`motor` 承担编码器闭环/速度环，`l298n` 无编码器设施，不是同一功能的两种实现） |
| 16 | `step_motor` × `sr04`/`hx711`/`at24c02`/`mq5` | 默认脚重叠（PB24/PB6/PB7/PB8）是「同选概率最低」设计，语义上步进执行 × 测距/称重/存储/气体完全不同框 |
| 17 | `ws2812` × `led` | `ws2812` mspm0 notes 明写「**刻意不叠灯族 LED PA15 板载灯——彩灯常代替板载灯做指示，同框概率高**」= 常互相替代？注意注释写的是「同框概率高」却**刻意不叠**——即设计者认为两者可能同选（彩灯做效果 + 板载灯做状态），**不并** |
| 18 | `max7219` × `led`（板载灯） | `max7219` stm32 notes「显示件与板载指示灯为**输出指示互替**（有数码管/点阵就不用板载灯）」——但 `led` 是多实例通用指示件（一题可能要点多颗状态灯），并入显示组会让「三色指示灯」被屏幕吃掉；**不并**（判定同 `led` × `beep` 的并列口径） |
| 19 | `st7789_para`/`lcd` 的 `BLK` × `beep`（PA15 同脚） | `st7789_para` notes「BLK=PA15（叠蜂鸣+语音——**输出指示互替**）」——同理不并（背光脚共享 ≠ 同一功能） |
| 20 | `syn6288` × `led`（PC14 黄灯同脚） | `syn6288` notes「与板载黄灯 LED_YELLOW 同脚：语音播报与指示灯为输出指示互替」——同理不并 |
| 21 | `zigbee_uart_key` × `zigbee_uart`/`zigbee_link` | **成对件**：key 是「无线身份识别/信标上报」的**发送侧**（`zigbee_uart` notes「与 zigbee_uart_key 配对」），两者要同时用在两块板上；现有组名「Zigbee 无线链路（**接收侧**）」明确只覆盖接收侧（同一路 RX 单消费者）——**不并**（发送侧无 RX 消费者冲突） |
| 22 | `coord_detect` × `k230` × `open_mv4` × `digit_uart` | 协议切片 + 视觉链路（帧解析），不属器件组；`open_mv4` notes 自证「并入 coord_detect 扩展**不推荐强并**——帧格式差异大」 |
| 23 | `adc` × `ads1115` | 板载 ADC 内部件 × I2C 外扩 ADC 器件（多路模拟采集），可共存（`ads1115` 是「外扩多路」不是「替代板载」）；`gp2y1014au` notes「ads1115 与本件不冲突」 |
| 24 | 内部件（`delay`/`config`/`uart`/`filter`/`ntb_time`/`debug_uart`/`adc` 等） | `library.MODULE_KIND` 登记为 INTERNAL/PROTOCOL 的件不承载赛题功能（能力方向判据③），不成组；`debug_uart` 是常备调试件、`adc` 是板载 ADC 属主（薄封装件依赖它而非替代它） |
| 25 | `joystick` × `adc` | `joystick` notes 明写「与 adc 模块 ADC_CH1/CH0 **ADC 共享组**（mspm0 MEM1/2 与 adc 共享同构）」= 合法共享，不是互替 |
| 26 | `us016`/`ir_distance` × `flame`/`mq*`（共读 PA5） | 见 #14：合法共读，非同类 |
| 27 | `bmp180`/`ms5611` × `motor`（stm32 共读 PA6/PA7） | 「气压/海拔与带电机方向的小车运动控制不同框、同选概率最低」——不同框，且 `motor` 与气压件不是同类功能 |
| 28 | `sr04` × `step_motor` | 「测距与步进同选概率最低」——不同框 |
| 29 | `hx711` × `motor`（PB5/PB0 同脚） | 「光电编码器闭环小车与静态称重不同框」——不同框 |
| 30 | `relay` × `motor`/`hx711` | 「继电器与带编码器闭环的电机控制不同框、同选概率最低」——不同框 |
| 31 | `relay` × `jq8900`/`syn6288`/`ws2812`（执行/输出件泛化） | 「输出」是过宽的口径（继电器控制负载、语音提示、灯带效果都是输出），并组会吃掉各自的独立价值；本表只收**同一功能槽位**（如「一声/一句提示」）——与 #37 同口径 |
| 32 | `esp01s` × `ec01g` | 一个是 WiFi 局域联网、一个是蜂窝广域；两者都是「联网上报」但介面/资费/范围不同，可共存（也都能与 `hc05` 并列）——若按 2.2 #3 口径拍板，本条同口径 |
| 33 | `nrf24l01` × `zigbee_link`/`as32` | `nrf24l01` stm32 notes「CLK=PB10/MOSI=PB11（ZIGBEE_UART+as32+key_matrix COL3/4——**无线数传互替件同脚先例**：2.4G 与 Zigbee/LoRa 二选一接入）」——**2.4G 点对点低速 vs 透传链路**存在真实差异（低延迟遥控 vs 数据透传），但库内自证「二选一接入」→ 若你按 2.2 #1 合并无线族，本条应一并纳入；**我建议一并纳入**（同一物理链路只能挂一件） |
| 34 | `hc05` × `nrf24l01` | 同上族内（蓝牙 vs 2.4G），差异真实；建议随 #33 同口径 |
| 35 | `uwb_uart` × `huidu`/`pid`/`xunji`（mspm0 默认脚同族 PA22-27） | `uwb_uart` mspm0 notes「UWB 全局定位 × 灰度巡线为方案互替/不同框」——「方案互替」指整车方案层面（定位车 vs 巡线车），不是同一功能的两种硬件；**不并** |
| 36 | `tp_xpt2046` × `lcd` | 触摸屏配套件（屏+触同选），`lcd`/`ili9341` notes 都写「与 tp_xpt2046 配套件**刻意错开**」——配套不是互替 |
| 37 | `relay`/`jq8900`/`syn6288` 的「输出执行件」泛化 | 「输出」是过宽的口径（继电器控制负载、语音提示、显示都是输出），并组会吃掉独立价值；本表只收**同一功能槽位**（如「一声/一句提示」）——判定与 #31 同口径 |

> 判定口径一句话：**「同一题会不会同时需要这两件？」——会，就不并；不会（二选一），才并。**

## 三、结论

1. **已并 4 组 / 13 个模块**：`display`（6）、`distance`（4）、`barometer`（2）、`sound-prompt`（2）。
   库内功能组从 3 个 / 8 个模块 → **7 个组 / 21 个模块**（`gray-track` 3、`attitude-hold` 3、
   `zigbee-rx` 2 为本轮之前已有）。
2. **判定「不并」37 条**（2.3 全表）——每条给了为什么，下一轮盘点不必重复产出同一批候选。
3. **待用户拍板 3 条**（无线族：LoRa×Zigbee、UWB×GPS、蓝牙×WiFi 手机遥控链路）+
   **备选 3 条**（NB-IoT、语音两件、温湿度族）——**未动手**，各带建议选项（2.2）。
4. **红证/绿证**：改前 7/8 红（4 组候选全红 + 3 条待拍板红，对照样例姿态组绿）；
   改后 4 组全绿（每组只剩一件 + 另一件进 `dropped_exclusive_members`），3 条待拍板仍红
   （`red-before.txt` / `green-after.txt`）。
5. **回归数值**：见文末「回归」段（`pytest` / `node --test` / `mypy` / `make-payload.py`）。

## 四、回归（2026-09-13 实测）

| 项 | 命令 | 结果 |
|---|---|---|
| 全量 Python | `$env:PYTHONPATH='src'; python -m pytest -q` | **4032 passed, 1 warning in 136.19s**（warning = fastapi/starlette 弃用提示，非失败）。基线对照：改前测试树 `--collect-only` = **4023**，本树 = **4032**（+9 = 本单新增的结构守卫 `tests/test_exclusive_group_gap_audit.py`，其余为基准值更新，零回归） |
| 全量前端 | `node --test tests/js/*.test.mjs` | **1467 pass / 0 fail**（前端本轮零改动） |
| 类型检查 | `$env:PYTHONPATH='src'; python -m mypy src/contest_generator/selection.py` | **Success: no issues found in 1 source file** |
| 组卡 fixture | `$env:PYTHONPATH='src'; python .scratch/group-choice-required/make-payload.py` | 组卡 `[('gray-track', ['pid'], []), ('attitude-hold', ['jy61p'], ['imu_uart'])]`——**每组 recommended ≤1**；两份 fixture（`payload.json` / `payload-ambiguous.json`）重跑后与既有内容**逐字节一致**（`git status` 无 diff） |
| 红/绿探针 | `python .scratch/exclusive-group-gap-audit/probe-group-convergence.py` | 改前 **7/8 红** → 改后 **3/8 红**（剩余 3 条 = 待拍板的无线族三条，探针里已标注） |
| 结构守卫 | `python -m pytest tests/test_exclusive_group_gap_audit.py -q` | **9 passed** |
| 真库基准 | `python -m pytest tests/test_module_universality.py -q` | **8 passed** |

## 五、留口

1. **待用户拍板 3 条**（2.2 表）：无线族并组要动 `zigbee-rx` 的组名语义 —— 拍板前不动手。
2. **`beep` 的 mspm0 条目是占位实现**（`pins` 空、`hardware_bound: true`）：`sound-prompt`
   在 mspm0 侧仍出卡（成员 ≥2），但要真正在 mspm0 上用蜂鸣器需先接线并按 `beep_stm32.c` 实现
   （模块自身留口，非本单范围）。
3. **`vl53l0x` × `tcs34725` 的 stm32 同址 0x29**：属**同址物理冲突**而非同类功能，本轮按
   不改引脚/不改 notes 的口径留原样（notes 已有记录，冲突走引脚绑定/换件消解）。
4. **`distance` 组收进了 `sr04`**（仅 mspm0、与 `us016` 同为超声波但接口不同）：库内文字
   没有直接写「sr04 × us016 互替」，依据是 `vl53l0x` notes 把四件归为「测距」一族 + 同物理量
   口径；如果你认为「超声波模拟量件」与「超声波 TRIG/ECHO 件」应当可共存，把 `sr04` 移出该
   组即可（一处 manifest + 两处测试基准）。

