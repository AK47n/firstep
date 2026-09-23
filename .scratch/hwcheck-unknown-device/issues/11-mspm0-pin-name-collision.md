# 11 — mspm0 引脚符号重名：任选两件就编不过，而门禁一声不吭

**要做什么：** 选中集的 mspm0 工程里，**同一趟出现的两个实例不许再有同名引脚符号**——要么母版把重名的引脚改名，要么生成前把它判成冲突并给出可执行的出路（照既有的 400 文案口径）。今天的状态是：SysConfig 直接报错、工程编不过，而**检测页与赛题页都没有任何提示**。

**被谁阻塞：** 无——可立即开始（发现于工单 04 的两平台编译矩阵，与 04 的改动无关）

**状态：** resolved

> ✅ **2026-09-23 已修**（判据前移：生成门禁 / 检测页 / 自动配置与校验端点四条路都在生成前大声失败，见下面「结论」）。
> ⚠ **仍留一条尾巴**：**母版改名**（让"OLED + 传感器"这类组合真的能用）没有做——本次只做了
> "如实拦下 + 说清出路"。所以撞名的组合**今天仍然不能同选**，这一点在 `CONTEXT.md`
> 与两条 400 文案里都写明了；要真正放开得另开一单（母版 `.syscfg` 的 `$name` 改名 +
> 别处对该符号的引用排查 + 全 mspm0 编译矩阵复跑）。

- [x] 母版 `mspm0.syscfg` 里重名引脚符号盘点清楚，逐组判"同趟真会撞"还是"结构上不可能同趟"（14 组清单见下）
- [x] 判据进**生成前**：选中集里两个实例的同名引脚 → 大声失败（400 中文，出路照检测页那三条）或自动改名，二选一，不许"生成了、编译时才炸"
- [x] **两条路都要判**：`/api/generate`（赛题主线，门禁 `check_syscfg_pin_conflicts`）与检测页（`hwcheck_pin_plan`，生成前 400）——同一条判据两处各算一遍就是"预览 200 → 生成 400"那类事（工单 03 已经踩过一次）
- [x] 真编译矩阵复跑：至少 `oled + jy61p`（今天 4 个 error）、`led_beep + gp2y1014au`（`LED` 重名）、`rc522 + nrf24l01`（`MISO`/`MOSI` 重名）三格 0 error / 0 warning，或按上面的裁决被生成前拦下
- [x] 既有守卫不破：`syscfg_pin_conflict_report`（同脚冲突那条）判据与文案不变；母版实测读数不受影响（改了 `.syscfg` 要复跑既有编译矩阵）
- [x] 反证：把改名/拦截拿掉 → 对应用例变红（读数记进本工单）

> **勾选口径**（评审整改后重述）：
> * 第 1 条的"14 组"是**组数**（`SCL`/`SDA` 那一组含 17 个实例，别把 17 当组数）。
> * 第 4 条按"**被生成前拦下**"那一支验收（四条路都拦），不是"编译绿"——本次没有改名。
> * 第 3 条起初做漏了：`/api/bindings/auto` 与 `/api/bindings/validate` 当时**没读**这份判据，
>   于是"点『自动配置』照常、点生成才 400"（P0 段点名的就是这个）。评审抓到后已补。

---

## 结论（2026-09-23，工单 11 已 resolved）

### 一句话

这条缺陷的真实形态不是"冷门组合"：**库内 17 件 I2C 器件共用 `SCL`/`SDA` 两个符号名**，
而 `rewrite` 只改 `$assign`（脚）**不改 `$name`（符号）**——所以撞名**改绑解不开**。
修复取"判据前移"：四条路都在**生成前**大声失败，点出是哪两件、说清"改绑解不开"。

### 交付物

| 落点 | 是什么 |
|---|---|
| `src/contest_generator/syscfg_model.py` | 新增**引脚符号文法**：`_SYSCFG_PIN_NAME_RE` + `SyscfgModel.pin_names`（实例 → 符号名，行序）。prune / rewrite 各自重新 parse，所以裁剪后判定天然只算活着的实例 |
| `src/contest_generator/syscfg_prune.py` | 判据本体：`_duplicate_pin_names`（prune 后模型上判同名）+ 报告新增 `name_lines` / `name_count` / `conflict_count` 两根轴；两个新入口 `syscfg_pin_name_conflict`（文本进）与 `syscfg_pin_name_conflict_for`（**母版目录进**——读盘也留在域层，见下面评审整改第 5 条） |
| `src/contest_generator/generator.py` | 生成门禁：两根轴两套文案（同脚 = Resource conflict，可改绑；重名 = Duplicate name，**改绑解不开**，只能去掉一件或改母版） |
| `src/contest_generator/hwcheck_board.py` | 检测页：同名那一支单独一套 400 文案 + 三条检测页做得到的出路（**不再**把用户支去"用引脚配置改绑"——那做不到） |
| `src/contest_generator/webapp.py` | `/api/bindings/auto` 与 `/api/bindings/validate` 也读同一判据 → "点自动配置照常、点生成才 400"这条分家补上 |
| `CONTEXT.md` | 「syscfg 文件模型」补 `$name` 文法（并点明 rewrite 不动它）；「硬件检测」补两根轴的取舍 |
| `tests/test_syscfg_prune.py` / `test_generator.py` / `test_hwcheck_board.py` / `test_webapp.py` | 判据层 / 生成门禁 / 检测页 / 两个端点，各一组正反用例（真库真母版） |
| `.scratch/hwcheck-unknown-device/probe-11-contest-dupname.py` | 复现 / 验收探针：四组组合（含票面点名的另两组），撞名的必须被拦、不撞名的必须真编译绿 |
| `.scratch/hwcheck-unknown-device/probe-11-guard-strength.py` | 反证探针（4 条注入 + 逐字节复原 + sha256 复核） |

### 验收读数

**四条路的行为**（`python .scratch/hwcheck-unknown-device/probe-11-contest-dupname.py`，
读数 `probe-11-contest-dupname.txt`）：

```
=== oled+mpu6050（期望照常生成）=== 生成 OK → 真编译 exit=0，Duplicate name 0 条
=== oled+jy61p（期望拦下）===
  生成期按预期拦下：SyscfgPinConflictError
    · SCL：jy61p(JY61P) × oled(OLED_SPI)
    · SDA：jy61p(JY61P) × oled(OLED_SPI)
    这一条**改绑引脚解不开**（撞的是符号名，不是脚）：去掉其中一件模块后重新生成。
=== led-beep+gp2y1014au（期望拦下）===
    · LED：gp2y1014au(GP2Y1014) × led(LED_BEEP)
=== rc522+nrf24l01（期望拦下）===
    · MISO：nrf24l01(NRF24L01) × rc522(RC522)
    · MOSI：nrf24l01(NRF24L01) × rc522(RC522)
=== 结论：撞名组合全被拦下 + 不撞名组合编译绿（两条腿都成立） ===
```

> **票面那句 `CLK` 更正是多余的**：`rc522 + nrf24l01` 撞的是 `MISO`/`MOSI` 两条，
> `CLK` 要 `max7219` 也进来才撞（母版里 `CLK` = MAX7219 / NRF24L01 / TP_XPT2046
> 三件共用）。以读数为准。

**反证读数**（`python .scratch/hwcheck-unknown-device/probe-11-guard-strength.py`，
读数 `probe-11-guard-strength.txt`）：

```
[2] 注入前（守卫在）：三条用例全 PASS
[3] 注入 A（重名判据整个关掉）        → RED ｜ [4] 复原 sha256 相等 ✓
[3] 注入 B（判在母版全文上、没裁剪）  → RED ｜ [4] 复原 sha256 相等 ✓
[3] 注入 C（两根轴并成一根）          → RED ｜ [4] 复原 sha256 相等 ✓
[3] 注入 D（检测页那支分支关掉）      → RED ｜ [4] 复原 sha256 相等 ✓
[5] 复原后复跑：三条全 PASS（回绿） ｜ [6] 收尾指纹：逐字节未变 ✓
结论：反证成立
```

**回归**：不撞名的组合（`oled + ml_mpu6050`）真编译 **exit=0 / 0 error / 0 warning**；
`tests/test_generator.py` 既有同脚冲突用例全绿（那一轴的判据与文案一个字未改）。

### 两处必须说清的取舍（已写进用户可见处）

1. **撞名的组合今天仍然不能同选**——本次只做"如实拦下"，没做母版改名。所以
   "OLED + 任意 I2C 传感器"这条路是**被明确拒绝**的，不是"能用了"。文案写明原因
   （母版里这两件的引脚符号同名）。
2. **改绑引脚解不开**——这不是"没做"，是**做不到**：`rewrite` 只改 `$assign` 的值，
   `$name` 是同一实例块里的另一个字段（`instance_render.py` 的先例也印证：同名 LED
   撞 LED_BEEP 时的修法是**改名**，不是改脚）。所以文案里**不许**出现"去引脚配置
   改绑"这条不存在的出路（第一版写了，评审实测四种绑定 `name_count` 恒为 2 后删掉）。

### code-review 两轴结论与整改

**Standards 轴**（4 硬违规 / 4 判断项）——**4 条硬违规全部整改**：

1. **🔴 我删掉了一条既有用例的 `def` 行**：新用例顶掉了 `test_syscfg_pin_conflicts_
   output_tree_corpus_judges_current_text` 的函数头，它的 docstring 与断言沦为下一个
   用例的尾巴——**静默丢了一条测试身份**（`-k` 再也点不到）。→ 恢复函数头，
   `--collect-only` 复核两个名字都在。
2. **🔴 出路里写了做不到的事**（"改绑到别的脚"解重名）：`$name` 与 `$assign` 是同一
   实例块里两个独立字段，实测四种绑定 `name_count` 恒为 2。→ 两处文案都删掉那条，
   改成"去掉一件 / 换一件；两件都要得改母版（已记本单尾巴）"。
3. **🔴 判据数字写错**（`17 组存量重名`）：17 是 `SCL`/`SDA` 那一组的**件数**，组数是
   **14**；同一份 diff 另一处又写 14，自相矛盾。→ 两处统一为 14 并注明口径。
4. **🔴 `parse_syscfg` docstring 说"四类文法…addModule"**：那个正则其实只在 `prune`
   里用（docstring 与实现不符，本仓 docstring 即契约）。→ 改成"实例声明 / `$assign` /
   `associatedPins[n].$name` / ADC 通道行"，注明 addModule 归 prune；模块头的契约
   清单同步补上新文法。

判断项当场收掉 3 条：轴分派判据（`if not report.lines`）在两个调用方各推一遍 →
`conflict_count` 成为判"报告空不空"的唯一入口；`_INSTANCE_LABELS` 提为模块常量
（原先每次调用重造）；`hwcheck_pin_message` 新分支的 docstring 补前置条件。
**留 1 条不改**：那两句事实（"改绑引脚解不开"）在两个模块里各出现一次——两处的
**出路**本就不同（检测页没有引脚配置入口），为一句事实再抽共享常量不值当。

**Spec 轴**（缺失 3 / 蔓延 2 / 实现不对 3）——**全部整改**：

1. **🔴 验收 3 只关一半**：`/api/bindings/auto` 与 `/api/bindings/validate` 没读这份
   判据 → "点自动配置照常、点生成才 400"，正是 P0 段点名的症状。→ 两个端点都接上
   （新入口 `syscfg_pin_name_conflict`，与门禁同一判据），端点用例正反各一组。
2. **🔴 验收 4 只跑了一格**：探针只测了 `oled+jy61p`。→ 扩到四组（含票面点名的
   `led_beep+gp2y1014au`、`rc522+nrf24l01`），并在读数里更正票面那句多余的 `CLK`。
3. **🔴 验收 6 没做**（工单零改动、状态未 claim）：→ 本结论 + 勾选口径 + 状态。
4. 蔓延两条当场收掉：误删的既有用例、未跟踪的临时探针（整理成 `probe-11-*` 入库）。
5. 实现不对三条：文案自相矛盾 / 数字写错 / 缩小可用组合未在用户可见处披露
   （后者补进 `CONTEXT.md` 与两份 400 文案）。
6. **评审之后我自己又撞出一条（全套件抓的）**：把 `read_master_syscfg` 从
   `hwcheck_board` import 回 webapp —— 那是**装配原语**，
   `tests/test_hwcheck_assembly_home.py` 的 import 面守卫当场红。→ 读盘这一跳也
   收进域层（`syscfg_pin_name_conflict_for`），端点只调一个名字。

### 范围外 / 留给后面的工单

* **母版改名**（真正放开"OLED + 传感器"这类组合）：改 `mspm0.syscfg` 里 `associatedPins`
  的 `$name`（改成实例前缀，母版里已有 `STEP_MOTOR.RST2` 这种先例），排查别处对这些
  符号的引用，复跑全 mspm0 编译矩阵 + 既有实测读数。**本单的判据留着**——改名之后
  它照样该在（防回归）。
* **同一个脚被两只实例占用**那一轴不动（既有判据与文案一个字未改）。
* **未上板**：本单证的是"生成前如实拦下 / 不撞名的组合编译绿"，不证器件真能应答。

---

## 实测（修复前，2026-09-23；两条路都撞）

**① 赛题主线**（`/api/generate` 那条路，探针
`.scratch/hwcheck-unknown-device/probe-11-contest-dupname.py`，跑一遍就有读数）：

```
=== oled+mpu6050 ===
  生成 OK → 真编译 exit=0，Duplicate name 0 条      ← 这一组没事：ml_mpu6050 走 I2C_0 实例，
                                                      它的脚叫 I2C_0_SCL，不与 OLED_SPI 撞
=== oled+jy61p ===
  生成 OK → 真编译 exit=2，Duplicate name 4 条
     >> error: JY61P(/ti/driverlib/GPIO) associatedPins[0].$name: Duplicate name: 'SCL' ...
     >> error: OLED_SPI(/ti/driverlib/GPIO) associatedPins[0].$name: Duplicate name: 'SCL' ...
```

**② 检测页**（`hwcheck_pin_plan`）：只勾 OLED + JY61P → 生成 200 → 编译 exit=2。

两条路表现一模一样：**判据缺失，不是判据算错**——修法同一处。

**母版里 14 组重名**（扫描口径：`.$name` 的路径含 `.associatedPins[`，按路径前缀取实例名，
同一取值出现在两个以上实例 = 一组）：

| 引脚符号 | 出现在哪些实例 |
|---|---|
| `SCL` / `SDA` | ADS1115、AGS10、AHT10、AT24C02、BH1750、BMP180、HMC5883L、**JY61P**、LCD、MLX90614、MS5611、**OLED_SPI**、PCA9685、QMC5883L、SGP30、SHT20、SHT30、TCS34725（**17 件**） |
| `CS` | LCD、MAX7219、OLED_SPI、RC522、TP_XPT2046 |
| `OUT` | HUMAN_IR、IR_BEAM、IR_REMOTE、IR_TX、MICROWAVE、RELAY |
| `CLK` / `DIN` | MAX7219、NRF24L01(=CLK)、TP_XPT2046 |
| `MOSI` / `MISO` | NRF24L01、RC522 |
| `DATA` | DHT11、DS18B20 |
| `DC` / `RES` | LCD、OLED_SPI |
| `LED` | GP2Y1014、LED_BEEP |
| `SCK` | HX711、RC522 |
| `TX` | JQ8900、SYN6288 |

**影响面**：`SCL`/`SDA` 那一组最要命——库内 17 件 I2C 器件**任选两件**（如 OLED + 任意
传感器）在地猛星上就是 4 个 error。这不是冷门组合，是每天都会走到的路。

**修法候选**（本单取 2，1 留下）：

1. **母版改名**：把 `<实例>.associatedPins[n].$name` 改成实例前缀（`OLED_SPI_SCL`、
   `JY61P_SDA`…）——母版里本来就有这一形态（`STEP_MOTOR.RST2` / `DC_MOTOR.AIN1`
   是前缀式的）。代价：跨模块共享面，要看有没有模块代码引用这些符号，并复跑全部
   mspm0 编译矩阵；
2. **判据前移**（本单）：撞上就 400 并给可执行的出路——代价是**缩小了可用组合**
   （OLED + 传感器仍不能同选，只是从"编不过"变成"生成前说清"）；
3. 两者都做（先拦后治）：短期 2、长期 1。**1 与 3 的后半段仍未做**，见票头那条尾巴。

**与工单 04 的关系**：04 的验收线是"自建件探测程序两平台 0 error / 0 warning"，
这条缺陷**独立于自建件**（最小复现里一个自建件都没有），故不在 04 内修；04 的
编译矩阵把 `all-library` / `all-recipes` 两格记为"已知受限形态"，读数与本条互指。
