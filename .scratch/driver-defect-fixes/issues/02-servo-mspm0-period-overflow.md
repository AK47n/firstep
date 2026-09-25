# 02 — 修库内驱动缺陷：`servo` × mspm0 的周期 640000 超过 16 位定时器量程（50Hz 出不来、大角度恒高）

**要做什么：** mspm0 侧 `servo_init()` 之后，`SERVO_PWM` 真的输出 **50Hz / 20ms 周期**的 PWM，
写 0° / 90° / 180° 都能落在周期以内——今天它直接 `DL_Timer_setLoadValue(SERVO_PWM_INST,
SERVO_PWM_INST_CLK_FREQ / SERVO_FREQ_HZ)` = **640000**，而该定时器是 16 位（SysConfig 的
`timerCount` 上限 65535、同仓 `step_motor` 就显式钳到 65535），`DL_TIMER_PWM_MODE_EDGE_ALIGN`
的语义是 `LOAD = period-1`，**没有钳位**（SDK `dl_timer.h` 的 `DL_Timer_setLoadValue` 只写寄存器）。
推断后果：周期被截断成 `640000 & 0xFFFF = 50176` ⇒ ≈1.57ms（≈638Hz），且 **≈96° 以上比较值超过
周期 → 输出恒高**，学生看到的是"舵机不动 / 只在某个角度能动"。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] **先复核再改（本单第一步，不许跳过）**：16 位量程这条证据链要落到 SDK/SysConfig 的真出处
      （`library/masters/mspm0/**` 里 `SERVO_PWM` 实例的定时器型号与 `timerCount`、
      `dl_timer.h` 里 `DL_Timer_setLoadValue` 与 `DL_Timer_initPWMMode` 的语义）；
      复核结论（成立 / 不成立 / 部分成立）**写进工单结论**，含你查的文件与行
- [ ] 修法取**与同仓同款写法一致**的那一种（二选一，选完在结论里说明理由）：
      ① 按 `step_motor` 先例把周期钳进量程并**同时**调整预分频使计数频率落在能表达 20ms 的档
      （计数频率 ≤ 3.2MHz 时 20ms = 64000 计数 < 65535）；② 改用 SysConfig 侧就配好的分频
      （`.prescale`），运行时只写周期与比较值。**不要**只加钳位——钳位会把 50Hz 变成别的频率，
      那是"不崩但也不对"
- [ ] 判据落成测试（`tests/test_module_servo.py` 既有缝）：
      ① 20ms 周期**能在该定时器的量程内表达**（用库内常量与 SysConfig 事实算，不照抄实现）；
      ② 180°（`SERVO_ANGLE_MAX`）的比较值 < 周期值（这条直接钉住">96° 恒高"）；
      ③ mspm0 与 stm32 的换算常量仍单源在 `servo.h`（既有守卫不许破）
- [ ] 两平台 API 对偶不破：`servo_init(uint8_t, uint8_t)` / `servo_set_angle(uint8_t, uint16_t)`
      签名与语义一字不动；stm32 侧（`TIM_4` + `PSC=71` → 1MHz）**不要**顺手改
      （除非复核发现它同样超量程——那就在结论里另记一条）
- [ ] **修好后回头改一处配方口径**：`hwcheck-specialize/08` 现在按 D1 让 mspm0 那格
      **不扫到 180°**（`servo_set_angle(0, 180)` 可能完全不动）；本单修好后那句限制可以撤掉
      ——谁先落地谁改，两边结论互相点名
- [ ] **反证**：把修好的分频 / 周期算法改回"`CLK_FREQ / 50` 直接写 LOAD" → 新用例必须红
- [ ] **真编译矩阵**：`py -3 .scratch/hwcheck-specialize/probe-compile-matrix.py --slugs servo`
      → 两格全 `[PASS]`（编译器 0 error / 0 warning，链接器告警另记）
- [ ] 上板状态如实写：**未上板**（本单证据 = 只读侦察 + SDK 复核；真机上"50Hz 出得来、180° 有
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
