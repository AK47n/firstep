# 04 — mspm0 跨族迁移（Tier B：数据裁决先行 + motor 双分支 + pin_family.h 渲染）

**What to build:** mspm0 PWM 跨外设族（TIMG↔TIMA）——排针上只挂 TIMA 通道的脚（如 PA28 仅 `pwm:TIMA0_C3`）可绑电机 PWM；模块 motor 代码 #if 双分支（DL_TimerG_* / DL_TimerA_*），族标志由生成器渲染 pin_family.h；pwm 门禁全类型级放开 + 两通道同实例门禁。

**Blocked by:** 03（pinwriter / pin_bindings / index.html 同缝——03 合 main 后再开）

**Status:** resolved（2026-08-15 PR #81 squash merged ecad183，主会话复核 + 1535 绿复跑）

## 需求

1. **数据裁决（第一步，决定成败）**：全表排针上 TIMA0/TIMA1 的 PWM 通道分布（boards/mspm0-dimx.json token 逐脚列 + 地猛星引脚图 PDF 交叉核对）。PWMAB 需 **C0+C1 同 TIMA 实例**两通道。裁决：
   - 若存在同实例 C0+C1 排针对 → 跨族可行，实施 2-8；
   - 若不存在（如 TIMA0 排针仅 C3）→ **跨族物理不可达**，本工单改为：pwm 门禁维持 03 同族口径，TIMA-only 脚的能力标注修正（pwm token 标注"无消费方实例"并灰显，前端加提示），记录裁决入 spec/ADR 补注，工单以数据修正闭环。
2. **pin_family.h 渲染（新机制）**：生成器在 copytree 后按绑定族渲染工程根 `pin_family.h`（`#define PWMAB_FAMILY_IS_TIMA 1/0`；未绑/同族 = 0，不变化不落盘）。母版 .cproject IncludePath 验证工程根可达（mspm0 工程根默认可达，工单验证）。
3. **motor.c 双分支**（library/modules/motor/code/motor.c）：PWMAB 相关 DL_TimerG_* 调用（:50/56 setCaptureCompareValue、:58-59 startCounter）改 `#if PWMAB_FAMILY_IS_TIMA` → DL_TimerA_* 对应（签名同形逐个映射）；IRQ 名（PWMAB_INST_IRQHandler 等实例名派生宏）随实例名不变零改动；include "pin_family.h"。
4. **pinwriter.py**：跨族迁移 = peripheral 字段 TIMG0→TIMA0（03 能力复用）+ 族标志计算喂 pin_family.h 渲染（绑定脚 token 族 != 默认族 → IS_TIMA=1）。
5. **pin_bindings.py**：mspm0 pwm 全类型级（删 03 同族限制）；新增 **PWMAB 两通道同实例门禁**（C0/C1 推导实例不同 → 400 中文）。
6. **index.html pinCanHost 镜像**：pwm 全类型级（有任意 pwm token 的脚可选；若数据裁决不可达则 TIMA-only 脚灰显 + 提示）。
7. **测试**：红证先行（族标志缺位编译错 / 两通道异实例 400 / 03 同族限制在位时跨族被拦）；绿证——绑 TIMA 脚对 → pin_family.h IS_TIMA=1 + syscfg peripheral=TIMA0 + 生成宏断言 + motor.c 双分支编译；默认不配 == 母版逐字节 + pin_family.h 不存在/为 0；新增 tests/test_pin_unlock_mspm0_cross.py。
8. **真机**：2024H ①不配回归 gmake 0 错；②绑 TIMA 同实例两通道脚对 → gmake 0 错 + 产物断言（pin_family.h / syscfg peripheral / ti_msp_dl_config.h PWMAB_INST 值）+ step_motor/其它模块回归不破；③两通道异实例 HTTP 400 零产物。运行级（电机真转）用户上板自验。

## 文件边界

- `src/contest_generator/pinwriter.py`、`src/contest_generator/pin_bindings.py`、`src/contest_generator/generator.py`（pin_family.h 渲染挂钩）、`src/contest_generator/errors.py`、`src/contest_generator/boards/mspm0-dimx.json`（能力标注修正）
- `library/modules/motor/code/motor.c`
- `index.html`（pinCanHost）
- `tests/test_pin_bindings.py`、`tests/test_pin_unlock_mspm0_cross.py`（新）
- 零母版 syscfg / stm32 侧改动；铁律：独立 worktree（03 合 main 后从最新 main 建）

## 验收

- [x] 数据裁决记录（TIMA 通道排针全表 + 结论 + motor.c 通用 API 实证）入 Comments
- [x] pytest 全绿 + mypy src 干净（1535 passed + mypy 41 文件 Success）
- [x] 红证已验 + 绿证（peripheral 字段断言 + 默认逐字节 + 跨族通道过滤）——tests/test_pin_unlock_mspm0_cross.py 7 用例；pin_family.h / motor 双分支按实证取消（偏差留痕）
- [x] 真机：不配回归 + 跨族绑定 gmake 全 0 错 + 两个 400 零产物（证据 .scratch/real-run/tierB_realrun.log）
- [x] 独立 worktree（.claude/worktrees/pin-full-unlock-04，03 合 main 后从 9cb9ad5 建）+ 提交 + 推送开 PR #81

## 数据裁决（2026-08-15，第一步）

**TIMA 通道排针全表**（boards/mspm0-dimx.json 逐脚列 + 引脚图 PDF 文本交叉核对，
两者一致）：

| 实例 | C0 | C1 | C0+C1 排针对 |
|---|---|---|---|
| TIMA0 | PA0、PA8、PB8 | PA1、PA7、PA9、PA22、PB9、PB20 | **PA0/PA1、PA8/PA9、PB8/PB9** |
| TIMA1 | PA15、PA17、PA28、PB2 | PA16、PA18、PA24、PA31、PB3、PB18 | **PA15/PA16、PA17/PA18、PA28/PA31、PB2/PB3** |

结论：**存在同实例 C0+C1 排针对 → 跨族物理可达**，实施 2-8 路线成立（非
"不可达退回灰显"分支）。

**附带实证（决定实施形状的关键发现）**：

1. 最小 syscfg `PWMAB.peripheral = "TIMA0"` + PA8/PA9 跑 sysconfig_cli →
   0 错，生成 `PWMAB_INST TIMA0` / `GPIO_PWMAB_Cx_IDX DL_TIMER_CC_x_INDEX`
   ——宏名与通道索引与 TIMG 同形态。
2. **motor.c 不需要双分支**：全库模块 grep 零 `DL_TimerG_*` / `DL_TimerA_*`；
   motor.c 只用 SDK 通用 `DL_Timer_*`（dl_timera.h/dl_timerg.h 均为
   `#define DL_TimerX_* DL_Timer_*` 重定向）。全量工程（默认十模块）手工
   置换 PWMAB→TIMA0 PA8/PA9 + DIGIT→UART3 PA14/PA13 + DCC→PB20 +
   DC_MOTOR BB→PA12 后 `gmake clean all` **0 错 0 警**（motor.c 零改动编译）。
3. 因此需求 2/3（pin_family.h 渲染 + motor.c #if 双分支）**前提不成立，取消**
   ——偏差已同步修正 spec（数据契约变化 + 关键事实）与 ADR 0012（决策 5）。

## 实施记录（2026-08-15，worktree pin-full-unlock-04）

- **pin_bindings.py**：`_mspm0_pwm_instances` 改全类型级——有 pwm token 的
  脚可绑（跨族放开），角色通道尾 `_C0`/`_C1` 仍按 endswith 过滤（`_C0N`
  等互补通道不匹配）；新增 `_check_mspm0_pwm_channel_pairs`——同 slug 下
  `_C0`/`_C1` 成对 pwm 角色两脚有效实例集按基名（TIMA0/TIMG0）交集必须
  非空，空 → 400"两通道必须同实例，请成对绑定"（只绑单脚、异实例、成对
  换位三种语义与 UART 对同款）。模块 docstring 同步 Tier B 口径。
- **pinwriter.py**：零改动——03 的 `_mspm0_peripheral_of` 已认 TIMG/TIMA，
  候选优先匹配现值、否则取首个，跨族绑定自然产出 `TIMA0`。
- **generator.py / errors.py**：零改动（两通道门禁走 PinBindingError，
  已登记 400）。
- **index.html**：`mspm0PwmAllowed` 从"同族过滤"改"通道过滤"（全类型级 +
  互补通道不算同通道），`pinMissReason` 同步（"该脚没有 pwm 通道 Cx"）。
- **spec / ADR 0012**：数据契约变化与关键事实修正（无 pin_family.h、模块
  通用 DL_Timer_*、TIMA 全表），ADR 决策 5 跨族条款改写为实证结论。
- **测试**：红证已验（两通道异实例 400 / 单脚换位 400 / 通道不匹配 400）——
  tests/test_pin_unlock_mspm0_cross.py 7 用例；test_pin_bindings.py 的 mspm0
  pwm 用例改全类型级预期（PA8/PA9 跨族合法、PB18 通道不匹配 400）；
  test_pin_unlock_mspm0_same.py 两处同步（PB18 文案 + TIMG12 同族换实例
  需成对绑 C0/C1）。全量 1535 passed + mypy src 41 文件 Success。
- **真机**（直接 generate + gmake，证据 .scratch/real-run/tierB_realrun.log）：
  ① 2024H 十模块不配回归——syscfg == 母版逐字节 + gmake 0 错 0 警 6.9s；
  ② +digit_uart/step_motor 跨族置换（PWMAB→TIMA0 PA8/PA9 + DIGIT→UART3
  PA14/PA13 + DCC→PB20 + DC_MOTOR BB→PA12——全排针 31/31 被默认布局占用，
  单角色换脚必撞，连带换位是唯一绿解，sysconfig_cli 已实证）——syscfg 八
  字段断言 + gmake 0 错 0 警 7.7s + ti_msp_dl_config.h `PWMAB_INST TIMA0` /
  `GPIO_PWMAB_C0_IDX DL_TIMER_CC_0_INDEX` 断言 + motor.o 存在（零改动编译）；
  ③ C0→PA8 × C1→PA13 两通道异实例 → 400"两通道必须同实例"零产物；④ C1→
  PA8 通道不匹配 → 400 零产物。运行级（电机真转）用户上板自验。

## Comments

- 2026-08-15 开工（Status claimed，主检出 9cb9ad5 建 worktree）。
- 文件边界实际改动：`src/contest_generator/static/index.html`（工单写
  index.html）；motor.c / generator.py / errors.py / boards JSON 零改动；
  另加 spec.md 与 ADR 0012 两处事实修正（偏差留痕所必需）。
- **合并复核**（PR #81 squash merged ecad183，主会话）：diff 逐项对工单——
  pwm 全类型级（通道 endswith 过滤正确排除 `_C0N`/`_C1N` 互补通道，PA8 只收
  TIMA0_C0、PB18 C2N/C1 无 C0 拒）；两通道同实例门禁按基名交集（C0×C1 各
  自通道过滤后 base 集交空 → 400 文案点名两通道与实例清单；单脚换位 / 成对
  换位语义与 UART 对同款）；index.html 镜像通道过滤；旧测试三处同步
  （同族 TIMG12 换位改 C0/C1 成对绑、PB18 文案改通道、PA8/PA9 跨族合法）。
  偏差裁决成立：数据裁决实证 motor.c 全库零 `DL_TimerG_*`/`DL_TimerA_*`（SDK
  两族头均为通用 `DL_Timer_*` 重定向宏），TIMA0 全量工程 clean all 0 错——
  pin_family.h / motor 双分支取消有据，spec 数据契约与 ADR 0012 决策 5 同步
  修正。合并后 main 复跑 1535 绿 40.2s + mypy src 41 文件干净。worktree
  pin-full-unlock-04 照例保留。
