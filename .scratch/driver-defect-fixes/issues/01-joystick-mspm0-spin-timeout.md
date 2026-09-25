# 01 — 修库内驱动缺陷：`joystick` × mspm0 的超时判据用"自旋次数"而不是时间（读数很可能恒 0）

**要做什么：** 学生接好摇杆、把杆放中间时，`joystick_read_x_percent()` / `read_y_percent()`
给出**中位附近的百分比**（而不是恒 `0`）——今天 mspm0 侧的 ADC 忙等超时按"循环圈数 50 次"
判，而 ADC12_0 是 8 槽 sequence，跑完一次转换要 ~1ms，50 次寄存器轮询只要几微秒 ⇒ **必然提前
返回**；更坏的是 `0%` 恰好又是"杆推到端点"的合法读数，学生分不清"坏了"与"推到端点"。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 先把判据立成**时间**（不是圈数）：超时上限 ≥ 一次完整 sequence 转换所需时间 × 安全系数；
      阈值要用**库内已声明的事实**算出来（`ADC12_0` 的槽数 / 采样时间 / ADC 时钟分频，
      见 `mspm0.syscfg` 的 `ADC12_0` 实例），别写魔法数
- [x] 测试（驱动级，照 `tests/test_module_joystick.py` 既有体例）：
      ① 超时阈值 ≥ 一次完整转换时间；② 超时分支**不再把"没采到"当成"采到 0"**
      （首圈超时时不许 `return 0` 冒充读数——要么重试、要么如实返回"本次无效"并让调用方知道）
- [x] 与 adc 模块的既有口径对齐或写明为什么不同：同实例的 `adc` 模块用**无超时忙等**
      （读数正常），摇杆要"实时"所以照立创原版改造过——两处口径差必须写在注释里
- [x] 两平台 API 对偶不破（`joystick_read_x/y/_percent/_sw` 签名一字不动；stm32 侧
      用母版 `adc_get`，**不要**为对齐而顺手改它的行为——除非实测它同样有问题）
- [x] **反证**：把阈值改回"50 次自旋"→ 新用例必须红（证明判据真的钉住了这一条）
- [x] **真编译矩阵**：`py -3 .scratch/hwcheck-specialize/probe-compile-matrix.py --slugs joystick`
      → 两格全 `[PASS]`（编译器 0 error / 0 warning，链接器告警另记）
- [x] 文档同步：`library/modules/joystick/manifest.json` 与头注释里那句"超时返回上次值"
      （现在实现是"返回已采样均值"，首圈就是 0）与**槽数口径**（manifest 写"四通道"、
      `joystick.h`/`.c` 写 sequence 四通道 / endAdd=3，而 `mspm0.syscfg` 是 **8 槽 / endAdd=7**）
      一并改成事实——改哪几句写在工单结论里
- [x] 上板状态如实写：本单的证据链是**只读侦察 + 代码常量核算**，侦察原文自标"推断，需上板"；
      修完照仓库惯例写"未上板"（真机验证归 `docs/agents/local-environment.md` 那条安排）

---

## Comments

### 2026-09-25 立案依据（recon 只读实测，不是推测）

- 侦察原文 = `.scratch/hwcheck-specialize/recon-03-actuators.md` §4 **D2**（含推理链与行号）。
- 事实链：
  - `library/modules/joystick/code/joystick.c:18` `JOYSTICK_ADC_TIMEOUT 50`（注释自己写着
    "忙等超时圈数"）；`:25-30` 的 `while (BUSY_ACTIVE) { if (--timeout <= 0) return sum / (i ? i : 1); }`
    ——**第一次采样（i=0）超时就 `return 0`**。
  - ADC12_0 是 **8 槽 sequence**、`setSampleTime0(..., 500)`、ADC 时钟 = ULPCLK/8 ⇒ 500 ADC 周期
    ≈ 125µs/槽，跑完整序列 ≈1ms（`mspm0.syscfg:1288-1313`）；而 50 次寄存器轮询只是几微秒~几十微秒。
  - 后果：`joystick_read_x/y()` 在 mspm0 上读到 **0**，而 `0%` 又是"杆推到端点"的合法读数
    ⇒ 学生无法区分"坏了"和"推到端点"（同实例的 `adc` 模块用无超时忙等，读数是好的）。
- 对配方的影响（**本单不修配方**）：`hwcheck-specialize/08` 那一格照 recon 的建议**不写探头**
  （照 `key` 先例），note 里如实提示"读数可能恒 0（D2），而 0% 又是合法读数"；本单修好之后，
  那条 note 与工单 08 的那句提示要跟着更新（谁先落地谁改，写在两边的结论里）。
- 相关但**不在本单**：`adc` 模块头注释说 MEM2/MEM3「adc_get 不开放」，实现只挡 `> ADC_Channel_7`
  ——注释与实现不一致（文档性，低危，见 recon-03 §4 D2 末段）。
- 为什么优先级最高：它是三件里**唯一会让"读数本身是假的"**的一条，而读数正是这一版专精面
  要给学生的东西；改法也最窄（一个阈值 + 一个首圈分支）。

### 2026-09-25 落地结论

**改法**（`library/modules/joystick/code/joystick.c`）：超时上限改成**按 syscfg 事实算出来的
时间**，等待循环按「µs 步进」计数——

| 常量 | 值 | 出处 |
|---|---|---|
| `JOYSTICK_ADC_SEQ_SLOTS` | 8 | `mspm0.syscfg` 的 `ADC12_0.startAdd=0` / `endAdd=7` |
| `JOYSTICK_ADC_SLOT_US` | 125 | `mspm0.syscfg` 的 `ADC12_0.sampleTime0 = "125 us"` |
| `JOYSTICK_ADC_SEQ_US` | 1000 | = 槽数 × 每槽（一次 `startConversion` 跑满整个序列） |
| `JOYSTICK_ADC_TIMEOUT_US` | 4000 | = 序列 × 安全系数 4 |
| `JOYSTICK_ADC_CYCLES_PER_US` | `CPUCLK_FREQ / 1000000u` | SysConfig 生成（32MHz ⇒ 32 周期 ≈ 1µs） |

- **每一步都是 1µs**：`DL_Common_delayCycles(JOYSTICK_ADC_CYCLES_PER_US)` 之后 `waited_us++`，
  退出界 = `waited_us >= JOYSTICK_ADC_TIMEOUT_US`——「等了多少」从此是时间，不是圈数。
- **失败有独立出口**：一圈都没采到 → `JOYSTICK_ADC_INVALID`（0xFFFF，`joystick.h` 新增）。
  它在 raw(0-4095) 与 percent(0-100) 两个合法域之外，**不再用 0 冒充读数**；一圈超时只是
  作废那一圈、换下一圈重试（共 `JOYSTICK_ADC_SAMPLES` 圈机会）。两个 percent 版经**唯一换算
  出口** `_joystick_to_percent()` 把哨兵原样传出去。
- **与 `adc` 模块的口径差写在驱动注释里**：adc 一次只读一件、可以无限忙等；摇杆连读两轴且会被
  骨架周期性调用，所以留一个「给足时间的上限」防 ADC 没使能时挂死骨架——正常路径走不到它。

**文档同步改了哪几句**（本单只改这几处）：
1. `joystick.h` 顶部：`sequence 四通道` → **八槽（startAdd=0 / endAdd=7，槽位 8/8 用满）**，
   并补 MEM3/MEM4-7 的归属；新增 `JOYSTICK_ADC_INVALID` 的定义与「只有 mspm0 侧有这个概念」
   的说明；四个读函数的行尾注释补「65535 = 本次无效」。
2. `joystick.c` 顶部：`sequence 四通道` → **八槽**；超时那段注释整体改写成上面的「时间判据」
   口径（含与 adc 的口径差）。
3. `manifest.json`（mspm0 notes）：`sequence 四通道` → **八槽 / endAdd=7**；把
   「`JOYSTICK_ADC_TIMEOUT 50` 超时」那句改成按时间立的超时 + 哨兵值；编译矩阵那行补上本单的
   复跑读数文件名；**顺手把因头文件加行而漂移的行号引用**（`joystick.h L26-31` / `L24` /
   `L29-30`、`joystick.c L53-61`）改成不依赖行号的散文（manifest 与测试同批改）。
4. `CONTEXT.md` 的 ADC12_0 行：`六通道（endAdd=5）` → **八槽（endAdd=7）**（复测报告记的
   「三处口径互不相同」至此收敛到 syscfg 的事实）。
5. 配方口径（`hwcheck_recipes.json` 的 joystick × mspm0 一格）：`read` 两行的 `unit` 补
   「65535=没读到」；`note` 的「失败模式」与「本单不修的驱动缺陷」两条按修后口径重写。
   stm32 那一格**一字未动**（驱动没动、也没有哨兵值这个概念）。
6. 工单 `hwcheck-specialize/08` 与它的落地记录：按「谁先落地谁改」补了后续说明。

**判据与读数**

- 新增两条驱动级判据（`tests/test_module_joystick.py`）：
  `test_joystick_mspm0_timeout_is_a_time_budget_not_a_spin_count`（独立复算序列时长，断言
  槽数/每槽时间 == syscfg 事实、上限 ≥ 2 倍序列、**循环退出界就是那个预算**、步长挂在
  `CPUCLK_FREQ` 上）、`test_joystick_mspm0_timeout_never_masquerades_as_a_reading`（采样函数
  的返回出口**只许有**「均值」与「本次无效哨兵」两个——只查 `return 0` 抓不住老实现的
  `return sum / (i ? i : 1)`；percent 换算只有一处出口且带守卫）。
- **反证**（`.scratch/driver-defect-fixes/probe-guard-strength-01.py` →
  `probe-guard-strength-01.txt`）：五条注入逐条让对应用例变红、每轮逐字节复原
  （sha256 复核一致）——①安全系数 4→/2；②槽数 8→4；③`return JOYSTICK_ADC_INVALID` → `return 0`；
  ④退出界换成字面量 `50`；⑤**整体退回旧形态**（50 圈自旋 + 首圈 `return sum/(i?i:1)`，
  工单点名的那条反证）⇒ 两条新用例同时红。
- **真编译矩阵**（`probe-compile-matrix.py --slugs joystick` → `probe-compile-matrix-01.txt`）：
  **mspm0 / stm32 两格全 `[PASS]`**，编译器 0 error / 0 warning、链接器 0 error / 0 warning，
  页面标记都是 `[专精]`（配方真的生效）。
- 相关面 pytest：`tests/test_module_joystick.py` + `tests/test_hwcheck_recipe.py`
  **213 passed / 10 skipped**。

**双轴评审的整改**（`code-review`，Standards + Spec 各一轮）：
- Standards：x/y 两个 percent 函数体逐字重复 → 抽成 `_joystick_to_percent()`；
  `got` → `got_samples`；行号引用漂移 → 改散文；读数行宽余量被吃 → `unit` 改短
  （123 → 121 字节，上限 128）；量具偏弱（`split(名字,1)[1]` 让 y 的守卫能喂绿 x 的断言）
  → 换成按签名切函数体的 `_c_functions()`。
- Spec：判据抓不住「循环里真在等」（只查常量与字符串，把界换成字面量 `50` 仍绿）→ 补
  「退出界 == `JOYSTICK_ADC_TIMEOUT_US`」断言 + 第 ④ 条注入；工单点名的反证没照做 → 补第 ⑤ 条
  注入；文案强于证据（把「很可能恒 0」写成事实）→ 驱动注释 / manifest / 配方 note 三处都恢复
  「按代码常量核算…仍未上板复核」的口径。

**上板状态：未上板。** 本单证据 = 只读侦察 + 代码常量核算 + 驱动级判据 + 真编译矩阵 + 反证；
「板上真的读到中位值、不再是 0」要真板子，归 `docs/agents/local-environment.md` 那条安排
（工单 `hwcheck-acceptance/05`）。

