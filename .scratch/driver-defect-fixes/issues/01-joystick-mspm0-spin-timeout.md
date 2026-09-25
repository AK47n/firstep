# 01 — 修库内驱动缺陷：`joystick` × mspm0 的超时判据用"自旋次数"而不是时间（读数很可能恒 0）

**要做什么：** 学生接好摇杆、把杆放中间时，`joystick_read_x_percent()` / `read_y_percent()`
给出**中位附近的百分比**（而不是恒 `0`）——今天 mspm0 侧的 ADC 忙等超时按"循环圈数 50 次"
判，而 ADC12_0 是 8 槽 sequence，跑完一次转换要 ~1ms，50 次寄存器轮询只要几微秒 ⇒ **必然提前
返回**；更坏的是 `0%` 恰好又是"杆推到端点"的合法读数，学生分不清"坏了"与"推到端点"。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] 先把判据立成**时间**（不是圈数）：超时上限 ≥ 一次完整 sequence 转换所需时间 × 安全系数；
      阈值要用**库内已声明的事实**算出来（`ADC12_0` 的槽数 / 采样时间 / ADC 时钟分频，
      见 `mspm0.syscfg` 的 `ADC12_0` 实例），别写魔法数
- [ ] 测试（驱动级，照 `tests/test_module_joystick.py` 既有体例）：
      ① 超时阈值 ≥ 一次完整转换时间；② 超时分支**不再把"没采到"当成"采到 0"**
      （首圈超时时不许 `return 0` 冒充读数——要么重试、要么如实返回"本次无效"并让调用方知道）
- [ ] 与 adc 模块的既有口径对齐或写明为什么不同：同实例的 `adc` 模块用**无超时忙等**
      （读数正常），摇杆要"实时"所以照立创原版改造过——两处口径差必须写在注释里
- [ ] 两平台 API 对偶不破（`joystick_read_x/y/_percent/_sw` 签名一字不动；stm32 侧
      用母版 `adc_get`，**不要**为对齐而顺手改它的行为——除非实测它同样有问题）
- [ ] **反证**：把阈值改回"50 次自旋"→ 新用例必须红（证明判据真的钉住了这一条）
- [ ] **真编译矩阵**：`py -3 .scratch/hwcheck-specialize/probe-compile-matrix.py --slugs joystick`
      → 两格全 `[PASS]`（编译器 0 error / 0 warning，链接器告警另记）
- [ ] 文档同步：`library/modules/joystick/manifest.json` 与头注释里那句"超时返回上次值"
      （现在实现是"返回已采样均值"，首圈就是 0）与**槽数口径**（manifest 写"四通道"、
      `joystick.h`/`.c` 写 sequence 四通道 / endAdd=3，而 `mspm0.syscfg` 是 **8 槽 / endAdd=7**）
      一并改成事实——改哪几句写在工单结论里
- [ ] 上板状态如实写：本单的证据链是**只读侦察 + 代码常量核算**，侦察原文自标"推断，需上板"；
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
