# 02 — 母版 mspm0 引脚符号去重：让「OLED 屏 + 任意 I2C 器件」真的能同选

**要做什么：** 学生在地猛星上勾着「OLED 屏」输出通道、再选一件库内 I2C 器件（AHT10 / BH1750 / SHT30 / JY61P…），
今天**生成前必被拦下**，出路只有"去掉一件"。撞的不是脚，是**引脚符号名**：母版把 OLED 的 SPI 变体两个脚
也叫 `SCL` / `SDA`，而库内 17 件 I2C 传感器实例逐字同名——SysConfig 要求同工程引脚符号唯一，
已实测**换四种引脚绑定 `name_count` 恒为 2**（改绑解不开）。本工单要把母版这一层解开，
让这类组合能同选、能生成、能真编译；并给"以后新增实例又撞名"留一道构建期守卫。

> 上游关系：`.scratch/hwcheck-unknown-device/issues/11-mspm0-pin-name-collision.md` 已经把"判据前移 +
> 如实拦下 + 说清出路"做完了，并在结论里**明写留了一条尾巴**：「母版改名（让"OLED + 传感器"这类组合真的能用）
> 没有做……要真正放开得另开一单（母版 `.syscfg` 的 `$name` 改名 + 别处对该符号的引用排查 + 全 mspm0 编译矩阵复跑）」。
> 本工单就是那条尾巴。

**被谁阻塞：** 无——可立即开始（与 01 互不阻塞，可并行）

**状态：** resolved

- [x] **先量影响面**（进 Comments，不许跳过）：改名会改掉哪些**生成的宏名**、哪些模块源码引用了它们
      （已知一例：`oled.c` 引用 `OLED_SPI_SCL/SDA_PORT` 与 `_PIN`）。量出的清单决定"改哪一侧面更窄"（读数见 Comments）
- [x] **裁决表**：工单 11 盘出的重名组（至少含 `SCL`/`SDA`=17 件 I2C 器件 × 显示件、`LED`=gp2y1014au × led_beep、
      `MISO`/`MOSI`=nrf24l01 × rc522、`CLK`=max7219 × nrf24l01 × tp_xpt2046）逐组给出"改名放开"还是"保留并如实拦下"，
      并写清判据（改名的代价 vs 该组合出现的概率）。**`SCL`/`SDA` 这一组必须在"改名放开"之列**（裁决表见 Comments）
- [x] 解开后的组合生成 200 且真编译 **0 error / 0 warning**：至少 `mspm0 + OLED 通道 + jy61p`（pilot 里的单平台 I2C 件）、
      `+ aht10`、`+ bh1750`、`+ sht30`，以及 `led-beep + gp2y1014au`（若裁决为放开）
- [x] **构建期守卫**：母版 `.syscfg` 新增一个与既有实例同名的引脚符号 → 当场红。判据**复用既有**的落盘冲突报告
      （`syscfg_pin_conflict_report` 的 `name_lines` / `name_count`），不另造一套
- [x] **反证探针**：把改名撤回（或再注入一个撞名实例）→ 守卫与组合用例必须变红；探针逐字节复原 + sha256 复核
      （照工单 11 的 `probe-11-guard-strength.py` 先例）
- [x] stm32 侧**零变化**（软 I2C 共挂同一条总线本来就合法，别把那边的判定带跑）
- [x] 母版改动后复跑既有 mspm0 编译矩阵（改了 `.syscfg` 就要重跑，工单 11 的既有纪律）
- [x] 同批更正 `CONTEXT.md`「硬件检测」「syscfg 文件模型」里"撞名改绑解不开、只能去掉一件"的措辞

---

## Comments

### 2026-09-24 量影响面（票面第一条，不许跳过）

量具 = `probe-02-impact.py`，读数 = `probe-02-impact.txt`。**结论：改名这条路只有
"改哪一侧"没有"改不改"的余地**——SysConfig 判据是 `$name` **全局唯一**，
`SCL`/`SDA` 那一组 18 个实例里只能留 1 个裸名，剩下 17 件照旧互相撞。

| 量什么 | 读数 |
|---|---|
| 重名组 / 撞名符号 / 涉及实例 | **14 组 / 68 个符号 / 35 个实例**（`SCL`/`SDA` 一组 18 个实例；工单 11 报 17——漏了 `PCA9685`） |
| 生成宏形态（真产物实测） | `<实例>_<符号>_<后缀>`（`OLED_SPI_SCL_PORT`/`_PIN`/`_IOMUX`，见 `matrix/A-oled+aht10/Debug/ti_msp_dl_config.h`） |
| 要同批改的 mspm0 源码 | **373 处 / 35 个文件** |
| **误改风险：stm32 侧同名不同源** | **187 处**（`pin_config.h` 的 `AHT10_SCL_PIN` 等——按 manifest 平台文件清单分开数才不会改错） |
| 模块目录之外 | 292 处 / 33 个文件（`tests/` 为主；`src/` 只 2 处 = `instance_render.py` 内嵌默认文本） |

### 2026-09-24 裁决表（逐组）

**依据不是"想改多少"，是实测**：`probe-02-combos.py`（读数 `probe-02-combos.txt`）
把票面点的那一格扩到 12 格，**10 格生成前就被拦下**——不止"OLED × 传感器"，
还有 `aht10 + bh1750`（环境站标配）、`oled + lcd`、`led_beep + gp2y1014au`、
`rc522 + nrf24l01`、`dht11 + ds18b20`、`hx711 + rc522`、`relay + human_ir`、
`jq8900 + syn6288`。只改 OLED 那两个符号名，这 9 格照旧是死的。

| 符号组 | 实例（消费模块） | 改名代价 | 组合出现的概率 | 裁决 |
|---|---|---|---|---|
| `SCL`/`SDA` | 18 件：15 件软 I2C 传感器 + `LCD` + `OLED_SPI` + `PCA9685` | ~300 处 | **必撞**：显示件默认勾选 × 任意传感器；传感器之间（温湿度+光照）也是日常搭配 | **改名放开**（票面硬要求） |
| `CS` | `LCD`/`MAX7219`/`OLED_SPI`/`RC522`/`TP_XPT2046` | ~26 处 | 两块 SPI 件同选（屏幕 + 读卡/点阵/触摸） | 改名放开 |
| `DC`/`RES` | `LCD`/`OLED_SPI` | ~10 处 | 大小屏同选（少见但合法）；与 `CS` 落在同批文件 | 改名放开 |
| `CLK`/`DIN` | `MAX7219`/`NRF24L01`/`TP_XPT2046` | ~25 处 | 点阵/触摸屏 + 无线（同批文件） | 改名放开 |
| `MOSI`/`MISO` | `NRF24L01`/`RC522` | ~15 处 | 无线 + 读卡（同批文件） | 改名放开 |
| `SCK` | `HX711`/`RC522` | ~15 处 | 称重 + 读卡（同批文件） | 改名放开 |
| `OUT` | `IR_BEAM`/`HUMAN_IR`/`IR_REMOTE`/`IR_TX`/`MICROWAVE`/`RELAY` | ~20 处 | 单脚输入件两两同选（人体红外 + 继电器 = 智能照明） | 改名放开 |
| `DATA` | `DHT11`/`DS18B20` | ~20 处 | 两件单总线测温同选（对比/冗余） | 改名放开 |
| `LED` | `GP2Y1014`/`LED_BEEP` | ~4 处 | 板载灯 + 粉尘传感器（票面点名的格） | 改名放开 |
| `TX` | `JQ8900`/`SYN6288` | ~6 处 | 两路语音同选（少见） | 改名放开 |

**没有一组需要"保留并如实拦下"**：`SCL`/`SDA` 那一组本身就占 373 处里的约 300 处，
其余 12 组的边际成本只有 ~70 处模块引用 + 测试期望；而全部改完换来一条**单一不变量**
（母版引脚符号全局唯一）与 spec 用户故事 7 要的构建期守卫——分开改既省不下文件、
又留下"一半撞名照旧由用户去掉一件来兜"的半成品。**这条与 spec.md ②「选面窄的那条」
不同**，已同批在 spec.md 那一节补记实测口径（见下 §口径更正）。

### 2026-09-24 立项依据

本仓 HEAD 实测（`.scratch/hwcheck-acceptance/probe-page.py`，读数 `exit-aht10.txt` 与 `probe-page.txt`）：

```
mspm0 + OLED 通道 + aht10  → 400（SCL/SDA：aht10(AHT10) × oled(OLED_SPI)）
mspm0 + OLED 通道 + bh1750 → 400（同上）
mspm0 + OLED 通道 + sht30  → 400（同上）
mspm0 + OLED 通道 + jy61p  → 400（同上；jy61p 是 pilot 10 件之一）
同上把 OLED 通道关掉        → 全部 200
```

而页面上「OLED 屏」**默认就是勾选的**，指南栏也建议"至少勾一个输出通道"——
所以最自然的一次上板（"我要屏幕看结果 + 我新买的那件传感器"）正好落在墙上。

根因定位（本仓 `library/masters/mspm0/mspm0.syscfg`）：`OLED_SPI.associatedPins[0].$name = "SCL"`、
`[1] = "SDA"`，而 `AHT10` / `BH1750` / `SHT30` / `JY61P` / `HMC5883L` / `AT24C02` / `ADS1115` /
`MLX90614` / `TCS34725` 等每个实例也都把自己的两个脚叫 `SCL` / `SDA`。

---

## 结论（2026-09-24，工单 02 已 resolved）

### 一句话

母版 14 组同名引脚符号（68 个符号 / 35 个实例）**全部改名放开**：撞名实例的
`$name` 一律改成 `<实例名>_<原符号>`（`SCL` → `OLED_SPI_SCL`），母版从此满足
"引脚符号全局唯一"这一条不变量。此前 12 格实测组合里 **10 格撞墙**（不止
"OLED + 传感器"），现在其中 12 格真编译全绿；判据一条没删，改成"注入重名现场"
继续守着。

### 先量影响面（票面第一条）

量具 `probe-02-impact.py`，读数 `probe-02-impact.txt`：

| 量什么 | 读数 |
|---|---|
| 重名组 | **14 组**（工单 11 报的是同一批；`SCL`/`SDA` 那一组**18 个实例**，不是 17——工单 11 的表漏了 `PCA9685`） |
| 撞名符号 / 实例 | 68 个符号 / 35 个实例 |
| 改名的 mspm0 源码代价 | **373 处 / 35 个文件**（改的是生成宏引用） |
| **误改风险（stm32 侧同名不同源）** | **187 处**——`pin_config.h` 里 `AHT10_SCL_PIN` 这类宏与 SysConfig 生成宏同名不同源，按 manifest 的平台文件清单分开数才不会顺手改错一片 |
| 模块目录之外 | 292 处 / 33 个文件（`tests/` 里的期望值与桩头为主；`src/` 只有 `instance_render.py` 的内嵌默认文本 2 处） |

生成宏的形态经真产物确认（`Debug/ti_msp_dl_config.h`）：`<实例>_<符号>_<后缀>`
（`OLED_SPI_SCL_PORT` / `_PIN` / `_IOMUX`）——所以改符号名 = 改宏名，模块源码必须同批改。

### 为什么是"全部 14 组"而不是"只改 OLED 那两个符号名"

`probe-02-combos.py`（读数 `probe-02-combos.txt`）把票面点的那一格扩到 12 格，
**10 格生成前就被拦下**：

```
[400/重名] oled＋aht10 / aht10＋bh1750（环境站） / aht10＋sht30 / oled＋lcd
[400/重名] led_beep＋gp2y1014au / rc522＋nrf24l01 / dht11＋ds18b20
[400/重名] jq8900＋syn6288 / hx711＋rc522 / relay＋human_ir
[200]      骨架（只有通道） / mpu6050＋aht10（硬 I2C 不撞软 I2C）
```

三条判据决定不做"窄修"：

1. **只改 OLED 的两个符号名救不了这一类**：另外 9 格照旧死——而
   `aht10 + bh1750`（温湿度 + 光照）是环境站标配，库内 notes 自己写着这两件"刻意
   不叠、常见组合"，等于设计上就该能同选；
2. **"每组留一件裸名"救不了 `SCL`/`SDA`**：18 个实例里只能留 1 个裸名，剩下 17 件
   照样互相撞——SysConfig 的判据是 `$name` **全局唯一**，没有"局部不撞"这回事；
3. **成本差得很小**：`SCL`/`SDA` 那一组本身就占 373 处里的约 300 处，"顺带"把其余
   12 组改掉的边际成本只有 ~70 处模块引用 + 测试期望；换来的是**一条单一不变量**
   （母版引脚符号全局唯一）与 spec 用户故事 7 要的那道构建期守卫。

### 裁决表（逐组）

判据 = 改名代价（该组涉及的 mspm0 引用处）vs 该组合出现的概率（实测能不能同选）。
**14 组全部"改名放开"**，没有一组需要"保留并如实拦下"：

| 符号组 | 实例（消费模块） | 改名代价 | 该组合出现的概率 | 裁决 |
|---|---|---|---|---|
| `SCL`/`SDA` | 18 件：15 件软 I2C 传感器 + `LCD` + `OLED_SPI` + `PCA9685` | ~300 处（最大的一组） | **必撞**：显示件默认勾选 × 任意传感器；传感器之间（温湿度+光照/气压+温湿度）也是日常搭配 | **改名放开**（票面硬要求） |
| `CS` | `LCD`/`MAX7219`/`OLED_SPI`/`RC522`/`TP_XPT2046` | ~26 处 | 两块 SPI 件同选（屏幕 + 读卡/点阵/触摸） | 改名放开 |
| `DC`/`RES` | `LCD`/`OLED_SPI` | ~10 处 | 大屏 + 小屏同选（少见但合法）；与 `CS` 同批一起改 | 改名放开 |
| `CLK`/`DIN` | `MAX7219`/`NRF24L01`/`TP_XPT2046` | ~25 处 | 点阵/触摸屏 + 无线（同批一起改） | 改名放开 |
| `MOSI`/`MISO` | `NRF24L01`/`RC522` | ~15 处 | 无线 + 读卡（同批一起改） | 改名放开 |
| `SCK` | `HX711`/`RC522` | ~15 处 | 称重 + 读卡（同批一起改） | 改名放开 |
| `OUT` | `IR_BEAM`/`HUMAN_IR`/`IR_REMOTE`/`IR_TX`/`MICROWAVE`/`RELAY` | ~20 处 | 单脚输入件两两同选（人体红外 + 继电器 = 智能照明） | 改名放开 |
| `DATA` | `DHT11`/`DS18B20` | ~20 处 | 两件单总线测温同选（对比/冗余） | 改名放开 |
| `LED` | `GP2Y1014`/`LED_BEEP` | ~4 处 | 板载灯 + 粉尘传感器（票面点名的格） | 改名放开 |
| `TX` | `JQ8900`/`SYN6288` | ~6 处 | 两路语音同选（少见） | 改名放开 |

> 改名代价里"与 `CS` 同批一起改"的意思是：这些实例的多个符号落在同一批文件里，
> 单改一组仍要动同一批文件——分开改没有省下任何东西。

### 改法与交付物

| 落点 | 是什么 |
|---|---|
| `library/masters/mspm0/mspm0.syscfg` | 68 行 `$name` 改成 `<实例名>_<原符号>`（+1 处注释里的旧宏名）；文件头补一段**命名规则与守卫指路** |
| 35 个模块的 **mspm0 文件**（36 个 .c/.h） | 生成宏引用同批改（`RC522_CS_PIN` → `RC522_RC522_CS_PIN`，共 379 处上下对称替换） |
| **27 个 manifest** 的 **mspm0 段 notes** | 提到的宏名同步（**stm32 段一个字没动**；改名器按花括号配对只动 mspm0 段） |
| `src/contest_generator/instance_render.py` | 内嵌的 mspm0 默认 `led_instances.h` 文本 + `_mspm0_pin_macro` 默认分支 |
| `src/contest_generator/syscfg_prune.py` | `_duplicate_pin_names` docstring：母版全文口径现在**立得起来**（改名后恒 0 组），守卫吃的就是这一口径 |
| `library/modules/led/code/led_instances.h` | 同上（渲染默认产物与盘上文件必须逐字节一致，既有用例钉着） |
| `tests/test_syscfg_prune.py` | 新增**构建期守卫** `test_master_pin_symbols_are_globally_unique`（复用 `syscfg_pin_conflict_report`，`manifests=()` 判母版全文，`name_count == 0`）；裁剪口径那条用例改成**双向对照**（同一母版：两件都选 → 报；只选一件 → 不报） |
| `tests/conftest.py` | 新增"重名回归现场"夹具（`collision_reverted_syscfg` / `collision_reverted_masters_dir` = 真母版 + 撤回一处改名；按「实例 + 当前符号」定位，不抄整行字面量） |
| 4 条真库用例 | 改成在注入现场上判：`test_syscfg_prune` / `test_generator`（含新正面用例 `test_mspm0_oled_plus_i2c_sensor_passes_the_gate`）/ `test_hwcheck_board`（+新正面用例）/ `test_webapp`（+真库 `ok:true` 对照腿） |
| 测试期望 **62 + 64 处**（另手改 3 张表 + 1 个桩） | 母版 `$name` 行 62 处（`rename-02-pin-labels.py --tests-only`）+ `MSPM0_DEFAULT_MAP` 64 处（`fix-02-test-tables.py`）+ `lcd`/`oled_spi`/`tp_xpt2046` 三张 `for` 循环表 + `hmc5883l` 的 mspm0 桩头 + `test_module_multi_instance` 两行 |
| `CONTEXT.md` | 「硬件检测」两根轴那段的措辞（18 件、已解开）+「syscfg 文件模型」补改名规则与守卫 |
| `docs/agents/local-environment.md` | §0 落差表「五批 → 六批」（本单）+ §2 会话注记（宏形态、造现场要借今天仍在用的原名、probe-09 会清 buildlogs） |
| `.gitignore` | `.scratch/hwcheck-acceptance/{matrix,tmp-matrix}/` 出索引（生成/编译产物可重建，按惯例不入库） |
| `.scratch/hwcheck-unknown-device/`（两处**标注**，不改原读数） | `probe-11-contest-dupname.py` 文件头 + `issues/11-*.md` 尾巴 ✅：本单翻转了那支探针的期望（真库不再有重名可抓），判据本体一条没删 |
| `.scratch/module-hwcheck/` | 既有 hwcheck 矩阵复跑：`probe-09-compile-matrix.txt` 刷新 + `probe-09-buildlogs/` 换成本轮 18 份（该探针按设计先清空上一轮，doc 已记这条） |
| `.scratch/hwcheck-acceptance/` | 量具/改名器/探针：`probe-02-impact.py`、`probe-02-combos.py`、`probe-02-compile-matrix.py`、`probe-02-reverse.py`、`rename-02-pin-labels.py`、`fix-02-test-tables.py` + 各自读数 |

### 验收读数

**编译矩阵**（`probe-02-compile-matrix.py`，读数 `probe-02-compile-matrix.txt`）：
**50 格全绿**——47 格 mspm0（12 格组合 + 35 格逐模块）0 error / 0 warning，
3 格 stm32（UV4）0 error / 0 warning。唯一两条告警是 `rc522.c` 里 `_antenna_off`
这个**既有死静态函数**的 `-Wunused-function`，基线版本
（`git show HEAD:library/modules/rc522/code/rc522.c`）里同样"定义了、没人调"，
与本次改名无关，探针把它单列一栏。

**既有矩阵复跑**（工单 11 的纪律）：`python .scratch/module-hwcheck/probe-09-compile-matrix.py`
—— 读数见 `probe-09-compile-matrix.txt`（本轮读数已刷新）。

**反证**（`probe-02-reverse.py`，读数 `probe-02-reverse.txt`）：

```
注入 A｜撤回一组改名（OLED_SPI + JY61P）→ 守卫 RED ✓、组合用例 RED ✓
注入 B｜再塞一个撞名实例（借既有的 TRIG）→ 守卫 RED ✓（新实例不必被选中就被抓到）
注入 C｜只撤回一边（阴性对照）          → 守卫 GREEN ✓、组合用例 GREEN ✓
复原：sha256 相等 ✓ ｜ 复原后两条用例回绿 ✓
```

> 注入 B 第一版写错了：借的符号写成 `SR04_TRIG`——02 只改了**撞过名**的符号，
> SR04 的符号本来就叫 `TRIG`，于是"撞"不起来（探针当场报 ✗）。**教训**：改名之后
> 想造重名现场，得借一个**今天仍在用的原名**（`TRIG`），不能按改名前的心智写。

**stm32 零变化**：改名器自校验（177 个 stm32 文件 sha256 逐字节不变）+
UV4 抽验 3 格（`aht10` / `hmc5883l` / `lcd`）0 error / 0 warning。

**套件**：`python -m pytest -n auto -q` **5359 passed + 1 skipped / 147s**（收尾最后一次全量；
母版头补注释后又专跑 `test_syscfg_prune` / `test_master*` / `test_pins` / `test_generator` /
`test_hwcheck_board` = **257 passed + 1 skipped**）。

### code-review 两轴结论与整改（2026-09-24）

**Standards 轴：硬性违规 0 条**（语言规范 / 工单格式 / 上下文更新义务 / 无残留旧宏引用全过）。
判断项 5 条，处置：

1. **Shotgun Surgery**（同一份符号知识四处副本：母版 + 模块源码 + manifest notes + 测试期望）
   ——**接受**（旧形态即缺陷，不存在"新旧并存"的 expand–contract 通道；有改名器 + 50 格编译矩阵 + 守卫兜底）。
   评审建议的补强（"模块 mspm0 源码引用的宏必须存在于母版"这道结构判据）**记进下面范围外**，不在本单加。
2. **Duplicated Code**（改名器两个"算计划"函数逐行重复）——**已改**：抽 `_plan_from_text(text)`，两条入口各一行。
3. **Primitive Obsession**（夹具重抄撤回循环 + 以整行字面量为键，母版重排即碎）——**已改**：
   抽 `_revert_pin_names(text)` 纯函数，按「实例 + 当前符号」regex 定位（两处夹具共用）。
4. **Mysterious Name**（`AHT10_AHT10_SCL_PIN` 这类双实例名）——**接受并已追认为规则**
   （CONTEXT.md「syscfg 文件模型」+ 母版文件头 + 本单「取舍」第 1 条）。
5. **参考库注释留旧名**（`library/references/**/at24c02.c` 3 份提到 `AHT10_SCL_IOMUX`）——
   **不在本单修**，见下面范围外（参考库是快照语料、不参与编译）。

**Spec 轴：核过成立 3 项 / 报 8 项，处置如下**：

1. spec ②「选面窄的那条」与实现不符 → **spec.md 那一节补记实测口径更正**（不是悄悄改口径：
   写清"12 格 10 格撞墙 + 全局唯一约束"两条依据，以及用户故事 7 的守卫因此才立得起来）。
2. 「先量影响面（进 Comments）」写进了 `## 结论` → **已在 Comments 段补两节**
   （量影响面 / 裁决表），结论段保留同一份内容的展开。
3. 交付物表漏列 `.gitignore` / `local-environment.md` / probe-09 日志刷新 → **已补**。
4. 验收清单被"同批改写后再勾选" → **已把注入的读数从清单里撤掉**，清单只留票面原文 +
   "读数见 Comments"这类指针。
5. 「24 个 manifest」实为 **27** → **已改**（工单 + `local-environment.md`）。
6. 「47 条测试期望」与自家读数不符 → **已改**为 `62 + 64 处（另手改 3 张表 + 1 个桩）`。
7. `test_duplicate_pin_names_are_judged_after_pruning` 在真母版上退化成恒绿空断言
   → **已改成双向对照**（同一份注入母版：两件都选 → 报；只选一件 → 不报），
   裁剪口径的判据重新有信号。
8. 反证读数里注入 B 的标题仍写"借 SR04_TRIG"（代码已改借 `TRIG`）→ **已修并重跑探针**。
9. 另核过成立：stm32 零变化、68 行 `$name`、50 格编译矩阵、10 格撞墙三条读数与读数文件相符。

### 必须说清的三处取舍

1. **宏名里实例名出现两次**（`AHT10_AHT10_SCL_PIN`）：SysConfig 生成宏 =
   `<实例>_<符号>_<后缀>`，而符号名必须**全局唯一**——要唯一就得带实例标识，两条
   约束相乘，重复不可避免。备选是数字后缀（`SCL2`/`SCL3`），但它依赖母版行序、
   读代码看不出是谁——比重复更坏。已写进 `CONTEXT.md`。
2. **判据一条没删**：`_duplicate_pin_names` 这条轴照旧在生成门禁 / 检测页 /
   自动配置 / 校验四条路上跑；四条真库用例改成"注入现场"继续守着（工单 11 说的
   "改名之后它照样该在（防回归）"）。将来若真有模块把引脚起成同名，学生看到的仍是
   那条如实拦下 + 出路文案（本批工单 03 会把它说成页面动作）。
3. **不动的东西**：stm32 的 `pin_config.h` 与全部 stm32 源码、模块 manifest 的
   stm32 段、`pin_config` 单源口径（软 I2C 共挂同一条总线本来就合法）。

### 范围外 / 留给后面的工单

* **被拦下时的出路文案**（"取消勾选那个通道"这类页面动作）：本批工单 03。
* **检测页 → 生成页的衔接入口**：本批工单 04。
* **真机上板**：本批工单 05（本单只证"能生成 + 能编译"）。
* **发现但不在本单修**：`rc522.c` 的 `_antenna_off` 是死静态函数
  （编译器每格都告警一次）——不是本次引入，另开修复单即可。
* **发现但不在本单修**：`library/references/**/at24c02.c` 三份快照的注释里还写着
  `照 AHT10_SCL_IOMUX 先例`（旧宏名）。参考库是**快照语料**（带来源/版权头、
  不参与编译、按批次整批入库），要不要跟着模块代码重刷是另一件事——本单不动它。
* **评审建议的补强（另立单）**：现在"母版改名要同批改模块源码"靠**人工纪律 +
  真编译矩阵**兜（本单 379 处替换即由此而来）。可考虑加一道结构判据：
  「模块 mspm0 文件清单里引用的 `<实例>_<符号>_{PORT,PIN,IOMUX}` 宏，必须在母版里
  找得到对应的实例+符号」——把这条纪律变成判据。本单不加（射程外，且要先把
  `I2C_0_INST` / `<实例>_PORT` 这类非角色宏的白名单口径定清楚，否则假红）。
