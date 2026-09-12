# 绑定判据单源下发（mspm0 板图「可配但必 400」修复）

## 问题陈述

「生成链路真机审计」P1 节对拍（`tests/browser/gen-chain-audit.mjs`）在 mspm0 平台上发现
**744 条（角色×脚）候选里有 115 条「板图显示可绑、后端必 400」**：

- 84 条 = `_check_mspm0_gpio_port_groups`（同模块同类型 gpio 角色默认同端口 → 吃单端口
  宏，如 `STEP_MOTOR_PORT`；混端口编译绿运行坏）；
- 31 条 = `_check_mspm0_pwm_channel_pairs`（PWMAB 两通道必须同外设实例）。

根因不是「前端漏了一条 if」，而是**判据分两处实现、且缺的这两条都是跨角色的
「组 / pair 级」约束**——前端 `pinCanHost` 的单脚判据结构上算不出它们。今天前端只镜子
「类型级 / 通道 / 实例」三层，于是 mspm0 上每个 io 脚都带 `gpio_out` token → step_motor
的 4 个 gpio 角色在 31 个脚上全绿，其中 A 口 21 个×4 = 84 条必 400。

用户影响：用户在板图上配得出一个绑定，走到最后一步点「生成工程」才被 400 拦下
（`/api/bindings/validate` 前置校验），且只给一条文案，不知道板图上还错在哪。

## 方案（用户 2026-08-xx 拍板：方案 B）

**后端单源回答「这个角色此刻能绑哪些脚」，前端只渲染。**

新端点 `POST /api/bindings/matrix`（形状在工单 04 实现中定稿，见该单）：

```
请求  {platform: "mspm0", slugs: [...], bindings?: {"<slug>.<role>": "<PIN>"}}
响应  {roles: [{role: "<slug>.<role>", type: "gpio_out", default: "PB24",
                selectable: ["PB24", ...],
                constraint: null
                          | {kind: "port",     port: "B", reason: "…"}
                          | {kind: "instance", instances: [...], pair: "…", reason: "…"}}]}
```

- **判据单源**：`selectable`（自身能力层：类型 / 实例 / mspm0 pwm 通道前缀）与
  `constraint`（跨角色谓词：gpio 端口组 / pwm 两通道同实例）都由后端**与门禁同一份判据**
  算出（`_strict_all_instances` / `_port_group_roles` / `_role_pair_mate`）——前端只求值、
  不复制规则。后端以后再加门禁，板图自动跟上。
- **判据随观测绑定变化**：`bindings` = 界面当前已配（`collectBindings` 同源）。未绑角色走
  默认——矩阵必须按「其余角色取有效脚」观测，否则会漏掉跨角色门禁（本单 115 条的成因）。
- **前端**：`pinCanHost` = 命中 `selectable` 且 `constraint` 谓词成立（`fx/pin-model.js` 纯
  函数）；`pinMissReason` 直接显示后端 `reason`（逐字中文）。判据未到 / 取失败 → 退回
  「类型级」旧口径（不假拦），板题注提示「正在核对可绑引脚…」/「判据加载失败」。

**范围（用户拍板）**：覆盖 gpio 同端口组 + 成对/通道同实例两类（115 条归零）。
槽位互斥（`_check_slot_conflicts`）本轮不进机制（它由 `resolve_bindings` 单绑定路径
自然带出，不做专项渲染）。stm32 走同一条通路（实测 600/600 无分歧 → 行为不变）。

## 用户故事

- 作为用户，我在板图上**点一个脚准备绑角色**时，若后端会拒，它必须是灰显 + 一句中文原因，
  而不是绿色可绑、到最后一步才炸。
- 作为用户，我把 `step_motor` 的第一个脚绑到 PB 口之后，板图上 A 口的另外三个候选**当场
  变灰**（组锁已定），我不会再配出必被拒的组合。
- 作为维护者，我**不想**在 `pinCanHost` 里再抄一遍后端规则；后端加一条门禁时，板图自动跟上。

## 实现决策

1. **不改 `resolve_bindings` 的既有出口**（validate / generate 文案逐字不变）：矩阵端点
   只调它、把 `PinBindingError` 文案变成 `reason`。
2. **不做纯常量矩阵**：判据依赖观测绑定（pair / 组），端点收 `bindings`。
3. **前端缓存 + 降级**：按 `(platform, slugs, bindings-json)` 缓存；取失败或未到时退回
   旧口径（`pinListsType` + 类型级），并在引脚卡提示「判据加载失败，按类型级显示」。
4. **审计脚本 P1 节保留**（真机对拍是最终判据），新增**离线对拍守卫**进 pytest
   （秒级、无浏览器）：钉「矩阵放行 ⊆ 后端接受」+「矩阵挡掉的 ± 后端一致」。

## 测试决策

- **契约测试**（`tests/test_bindings_matrix.py`，新）：
  - 端点形状 / 空 bindings / 坏平台 400 / 未知 slug 400；
  - 观测语义：`motor.PWMAB_C0 → PA0` 在 C1 未绑时 `ok:false`（成对）；把 C1 绑到同实例脚后
    同一格 `ok:true`；
  - 组锁语义：`step_motor` 四角色在 A 口脚上 `ok:false`、B 口 `ok:true`；第一个角色绑到
    A 口后（若组默认 B 口 → 该绑定本身该 false）……以真 `resolve_bindings` verdict 为准断言。
- **对拍守卫**（`tests/test_pin_matrix_parity.py`，新）：744 条候选逐条比
  「矩阵 ok」× `resolve_bindings` verdict：**放行但后端拒 = 0**（硬红线）、
  **挡掉但后端收 = 0**（假红，同一用例一起钉）。stm32 同款。
- **真机**：`node tests/browser/gen-chain-audit.mjs P` 的 P1 从 FAIL→PASS。
- **反向验证**：临时停用矩阵（`pinCanHost` 走旧口径）→ 对拍用例与 P1 必须当场变红。

## 范围外

- 槽位互斥（`_check_slot_conflicts`）不纳入本轮渲染机制。
- 多实例选脚（`instancePinTarget`）路径的候选过滤仍走「模块首 pin 能力」旧口径。
- 不改 `/api/bindings/validate` / `/api/bindings/auto` / `/api/generate` 的请求与响应形状。
