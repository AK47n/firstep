# 02 — 修库内驱动缺陷：`servo` × mspm0 的周期 640000 超过 16 位定时器量程（50Hz 出不来、大角度恒高）

**要做什么：** mspm0 侧 `servo_init()` 之后，`SERVO_PWM` 真的输出 **50Hz / 20ms 周期**的 PWM，
写 0° / 90° / 180° 都能落在周期以内——今天它直接 `DL_Timer_setLoadValue(SERVO_PWM_INST,
SERVO_PWM_INST_CLK_FREQ / SERVO_FREQ_HZ)` = **640000**，而该定时器是 16 位（SysConfig 的
`timerCount` 上限 65535、同仓 `step_motor` 就显式钳到 65535），`DL_TIMER_PWM_MODE_EDGE_ALIGN`
的语义是 `LOAD = period-1`，**没有钳位**（SDK `dl_timer.h` 的 `DL_Timer_setLoadValue` 只写寄存器）。
推断后果：周期被截断成 `640000 & 0xFFFF = 50176` ⇒ ≈1.57ms（≈638Hz），且 **≈96° 以上比较值超过
周期 → 输出恒高**，学生看到的是"舵机不动 / 只在某个角度能动"。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] **先复核再改（本单第一步，不许跳过）**：16 位量程这条证据链要落到 SDK/SysConfig 的真出处
      （`library/masters/mspm0/**` 里 `SERVO_PWM` 实例的定时器型号与 `timerCount`、
      `dl_timer.h` 里 `DL_Timer_setLoadValue` 与 `DL_Timer_initPWMMode` 的语义）；
      复核结论（成立 / 不成立 / 部分成立）**写进工单结论**，含你查的文件与行
- [x] 修法取**与同仓同款写法一致**的那一种（二选一，选完在结论里说明理由）：
      ① 按 `step_motor` 先例把周期钳进量程并**同时**调整预分频使计数频率落在能表达 20ms 的档
      （计数频率 ≤ 3.2MHz 时 20ms = 64000 计数 < 65535）；② 改用 SysConfig 侧就配好的分频
      （`.prescale`），运行时只写周期与比较值。**不要**只加钳位——钳位会把 50Hz 变成别的频率，
      那是"不崩但也不对"
- [x] 判据落成测试（`tests/test_module_servo.py` 既有缝）：
      ① 20ms 周期**能在该定时器的量程内表达**（用库内常量与 SysConfig 事实算，不照抄实现）；
      ② 180°（`SERVO_ANGLE_MAX`）的比较值 < 周期值（这条直接钉住">96° 恒高"）；
      ③ mspm0 与 stm32 的换算常量仍单源在 `servo.h`（既有守卫不许破）
- [x] 两平台 API 对偶不破：`servo_init(uint8_t, uint8_t)` / `servo_set_angle(uint8_t, uint16_t)`
      签名与语义一字不动；stm32 侧（`TIM_4` + `PSC=71` → 1MHz）**不要**顺手改
      （除非复核发现它同样超量程——那就在结论里另记一条）
- [x] **修好后回头改一处配方口径**：`hwcheck-specialize/08` 现在按 D1 让 mspm0 那格
      **不扫到 180°**（`servo_set_angle(0, 180)` 可能完全不动）；本单修好后那句限制可以撤掉
      ——谁先落地谁改，两边结论互相点名
- [x] **反证**：把修好的分频 / 周期算法改回"`CLK_FREQ / 50` 直接写 LOAD" → 新用例必须红
- [x] **真编译矩阵**：`py -3 .scratch/hwcheck-specialize/probe-compile-matrix.py --slugs servo`
      → 两格全 `[PASS]`（编译器 0 error / 0 warning，链接器告警另记）
- [x] 上板状态如实写：**未上板**（本单证据 = 只读侦察 + SDK 复核；真机上"50Hz 出得来、180° 有
      对应脉宽"这一步要示波器 / 逻辑分析仪，归 `docs/agents/local-environment.md` 那条安排）

---

## Comments

### 2026-09-25 立案依据（recon 只读实测，原文自标"推断，需上板/SDK 复核"）

- 侦察原文 = `.scratch/hwcheck-specialize/recon-03-actuators.md` §4 **D1**（含完整事实链与行号）。
- 事实链：
  - `SERVO_PWM` 时钟 = 32MHz（生成产物 `SERVO_PWM_INST_CLK_FREQ = 32000000`）；
  - `library/modules/servo/code/servo_mspm0.c:9-12` `servo_period()` = `32000000 / 50 = 640000`；
  - `:25` `DL_Timer_setLoadValue(SERVO_PWM_INST, servo_period())`，**没有钳位**
    （同文件 `:17` 的注释自己写着"period 最大 ~1.6e6（80MHz/50）"——作者知道这个数可以很大）；
  - SDK `dl_timer.h` 的 `DL_Timer_setLoadValue` 只做 `gptimer->COUNTERREGS.LOAD = value;`（无钳位），
    而 `DL_TIMER_PWM_MODE_EDGE_ALIGN` 的语义是 `LOAD = period-1`；
  - 同仓旁证"量程是 16 位"：`mspm0.syscfg:109` 的 `timerCount` 写成上限 65535；
    **同款写法的 `step_motor` 显式钳位**：`library/modules/step_motor/code/step_motor.c:49`
    `period = period < 65536 ? period : 65535;`——servo 没有这一步。
- 若 LOAD 真被 16 位截断：`640000 & 0xFFFF = 50176` ⇒ 周期 ≈ **1.568ms（≈638Hz）**而不是 20ms；
  90° 的比较值 48000 勉强 < 50176、**≈96° 以上超过周期 → 输出恒高**、180° = 80000。
- 库内测试**测不到**它：`tests/test_module_servo.py:139-146` 自己就用 `period = 640000` 算占空比
  ——所以这条守卫必须换判据面（"能不能在量程内表达"），照抄实现算不出红。
- 对配方的影响（**本单不修配方**）：`hwcheck-specialize/08` 的 mspm0 那格刻意不扫 180°
  （避免学生把"不动"读成"舵机坏了"）；本单修好后该限制可撤，见工单 08 的 Comments。
- 相邻但**不在本单**：`servo` 的 `servo_id` / `channel` 形参被实现 `(void)` 丢弃
  （recon-03 §4 D5，"多舵机是假接口"）——那是接口设计问题，另开单。

### 2026-09-25 落地结论

**第一步：复核（成立）。** 16 位量程这条证据链落到 SDK 的真出处（都在本机
`C:\ti\ccs2051\mspm0_sdk_2_10_00_04`）：

| 事实 | 出处 |
|---|---|
| `TIMG` = **16-bit counter + 8-bit prescaler**；`TIMG12` = 32-bit counter **without a prescaler** | `source/ti/driverlib/.meta/pwm/PWMTimerMSPM0.syscfg.js` 的 longDescription |
| `timerCount > 65535` 时元数据直接报错（文案点名「non-TIMG12 bounds」） | 同上，`validation.logError("Timer Count Exceeds non-TIMG12 bounds…")` |
| `DL_Timer_setLoadValue` 只做 `gptimer->COUNTERREGS.LOAD = value;`（**无钳位**），且文档明写「Refer to the device datasheet to determine the bit width of the counter」 | `source/ti/driverlib/dl_timer.h` |
| `DL_TIMER_PWM_MODE_EDGE_ALIGN` 的语义是 **LOAD = (period - 1)** | 同上，`DL_Timer_PWMConfig` 的 `period` 字段说明 |
| `clockPrescale` 映射成 `.prescale = clockPrescale - 1`，且 `_INST_CLK_FREQ` 是**折过预分频**的计数时钟 | SDK 官方例程 `LP_MSPM0G3507/driverlib/timx_timer_mode_pwm_edge_sleep`（`clockPrescale = 256` ⇒ 生成头里 `PWM_0_INST_CLK_FREQ = 125000 = 32MHz/256`） |
| 对照：同族的「32 位」例程用的是 **TIMG12** 且 `timerCount = 512000` | `timg_32bit_timer_mode_pwm_edge_sleep` |

⇒ **结论：成立**（不是"部分成立"）：SERVO_PWM 是 TIMG8 = 16 位，旧实现直写 640000 会被截成
50176、周期 ≈1.568ms（≈638Hz），且 ≈96° 以上的比较值超过周期 ⇒ 输出恒高。

**第二步：修法取「用母版侧配好的分频」（工单的二选一之②）**，理由：
① 与同仓 `PWMAB`（`clockPrescale = 256` + 小 `timerCount`）是**同一个既有写法**，不新造机制；
② 运行时零算法改动——`servo_period()` 仍然是 `SERVO_PWM_INST_CLK_FREQ / SERVO_FREQ_HZ`，
   而那个宏本来就折过预分频（SDK 例程实证），**只写周期与比较值**；
③ 工单明确否掉了「只加钳位」：钳位会把 50Hz 变成别的频率（不崩，但也不对）。
`servo_mspm0.c` 另加**编译期 `#error`** 把量程钉死（分频被改小 / 换 32MHz 直供就编不过），
并把 `DL_Timer_setLoadValue` 的入参改成 `servo_period() - 1u`（EDGE_ALIGN 的 `LOAD = period-1`，
与 stm32 的 `ARR = 1000000/fre - 1` 对偶）。

**改了什么**

1. `library/masters/mspm0/mspm0.syscfg`：`SERVO_PWM.clockPrescale` 1 → **16**、
   `timerCount` 65535 → **40000**（20ms @2MHz），注释写清量程依据与"不能是 1"的理由。
2. `library/modules/servo/code/servo_mspm0.c`：新增 `SERVO_TIMER_MAX_COUNT` 与编译期
   `#if … > SERVO_TIMER_MAX_COUNT` / `#error`；`LOAD` 改 `period - 1`；顶部注释补量程事实链。
3. `library/modules/servo/manifest.json`：mspm0 notes 补「量程约束（改母版前必读）」一段；
   description 里那句 `servo_init()` / `servo_set_angle(angle)` **与实际双参签名不符**
   （recon-03 §4 D6 记的漂移）同批改成事实，并注明两个形参当前都未使用。
4. `library/hwcheck_recipes.json`：`servo × mspm0` 的 `prereq` 从**三段**补成**四段**
   （0°→90°→180°→0°）——当年"先别扫 180°"的限制随修复撤掉；两格 note 里的段数说明
   与「本单不修的驱动缺陷（D1）」那条一并改成修后口径。`servo × stm32` 的
   `include` / `init` / `probe` / `read` / `console` 一字未动。
5. `tests/test_module_servo.py`：新增两条判据（见下）。

**判据与读数**

- `test_servo_mspm0_period_fits_the_16bit_counter`：**按 syscfg 的事实独立复算**——
  `clockPrescale` × BUSCLK（32MHz，母版 `SYSCTL.forceDefaultClkConfig = true`）⇒ 计数时钟，
  再算 20ms 的计数值，断言 **≤ 65535**，并断言 180° 的比较值**严格小于**周期值。
  （复算不照抄实现：实现里只有 `SERVO_PWM_INST_CLK_FREQ / SERVO_FREQ_HZ`。）
- `test_servo_mspm0_runtime_guards_the_counter_range`：断言编译期 `#if` + `#error` 在位、
  且**不许出现钳位**（`< 65536` 之类），以及 `LOAD = servo_period() - 1u`。
- **量具（实测，不是推断）**：`.scratch/driver-defect-fixes/probe-02-inst-clk-freq.py` →
  `probe-02-inst-clk-freq.txt`——真生成一份 servo 单选 mspm0 检测工程、跑 gmake（内含
  `sysconfig_cli`），从**生成产物**里读回：`SERVO_PWM_INST_CLK_FREQ = 2000000`、
  `.prescale = 15`、`.period = 40000`，三项与判据面逐项相等，且 40000 < 65535。
- **反证**：`.scratch/driver-defect-fixes/probe-guard-strength-02.py` →
  `probe-guard-strength-02.txt`——三条注入逐条让对应用例变红、逐字节复原（sha256 一致）：
  ① `clockPrescale` 改回 1；② 把 `#if` 阈值改成 `0u`（等于关掉守卫）；③ `LOAD` 退回
  `servo_period()`（少减 1）。
- **真编译矩阵**：`probe-compile-matrix.py --slugs servo` → `probe-compile-matrix-02.txt`：
  **两格全 `[PASS]`**，编译器 0 error / 0 warning、链接器 0 warning。
- `tests/test_module_servo.py` + `tests/test_hwcheck_recipe.py` **218 passed / 10 skipped**。

**上板状态：未上板。** 「50Hz 出得来、180° 有对应脉宽」要示波器 / 逻辑分析仪，归
`docs/agents/local-environment.md` 那条安排（工单 `hwcheck-acceptance/05`）。
**仍然不修**（照旧只提示）：`servo_id` / `channel` 假接口（D5）——本单只动周期量程。

**双轴评审的整改**（`code-review`，Standards + Spec 各一轮）：
- Standards：`servo_mspm0.c` 那条 `#error` 是这批里唯一的英文串 → **保留 ASCII**（编译器诊断会
  原样进构建日志，多字节代码页的编译器对非 ASCII 诊断串历来不稳），但在注释里**写明这是有意的**；
  配方文案「本格扫到 180° 就是它的验收」**强于证据** → 改成"扫到 180° 是**编译期**验收，
  板上真转没转仍未上板"。
- Spec：反钳位判据只匹配字面 `"65536 ?"`，**换个写法就能绕过** → 换成「源码里不许存在对周期值的
  比较（`period <…` / `period >…`）」这条形态判据，并补一条注入（改用三元钳位）证明它会红。
- 评审同时**核过站得住的三条**（避免我重复怀疑）：16 位结论与 SDK 原文逐条吻合；
  `LOAD = period - 1` 没有算错占空比（duty 是绝对计数，0/90/180° = 1000/3000/5000）；
  `servo × mspm0` 的 `prereq` 加 180° 属工单 02 第 31 行点名的口径。


