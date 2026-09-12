# 05 — 成对联动搬：让 uart/i2c 对在界面上真的搬得动（工单 04 的直接后续）

**要做什么：** 补「成对角色一起搬」的交互——用户在板图上把 `x.TX` 点到另一实例的脚时，
**同一次提交里**把 `x.RX` 也写到同实例的对应脚（或给一个「整对搬」的动作），否则工单 04 之后
成对角色在界面上等于钉死在原实例上。

**被谁阻塞：** 无（工单 04 已 resolved）。
**状态：** resolved（2026-09-12；形状 1「点一脚自动带上对脚」；`tests/js/*.test.mjs`
1526 passed（+7）、`python -m pytest -q` 4195 passed（+4）、真机审计 P 节 FAIL 0 /
WARN 0 / PASS 15）

**建议模型档：** high（改动集中在 `ui/generate-pins.js` 的绑定交互 + `pin-model.js` 的
「成对跟随」判定，缝不大但需要真机走查）

## 背景（工单 04 的实测记账，别当 bug 修）

后端 `_check_paired_role_instances` 的语义是「**成对**角色的两脚有效实例集交集非空」——
它看的是**整份 bindings**，所以：

- `debug_uart.TX → PA28`（UART0）单脚搬：后端**本来就拒**（TX UART0 × RX 默认 PA22 UART2
  交集空）——不是模型造出来的，实测见 `.scratch/mspm0-slot-conflict/probe_debug_uart_walk.py`；
- `TX→PA28 + RX→PA1`（同 UART0）整对搬：后端**收**；
- 而界面是**单角色绑一脚**（`bindRole(key, pinName)` 一次只写一个 key），
  没有「成对同时写」的路径 → 用户走不出第一步。

工单 04 把模型改成严格镜像门禁（全库 188+52+37 条假绿归零）之后，这一条就浮出来了：
**「点得下去但必 400」换成了「点不下去且说不清怎么搬」**——诚实但不可用，所以要有本单。

量表（`.scratch/mspm0-slot-conflict/probe_pair_lockdown.py`）：

- mspm0 全库 **14** 个 uart/i2c 对：**全部**在默认实例里还有第二个位（可搬，但必须成对搬）
  ——例如 `as32` TX `PA26`↔`PB2/PA14`、RX `PA25`↔`PB3/PA13`；
- stm32 **13** 个 uart 对：每实例只有一对脚（`PA9/PA10`、`PB10/PB11`、`PA2/PA3`），
  原地即唯一解 → 无影响；
- stm32 i2c **16** 对：脚不带实例 token，门禁跳过（工单 04 也不发谓词）→ 无影响。

## 拍板与形状（用户 2026-09-12 拍板取形状 1）

1. **点一脚时自动带上对脚**（采用）：`pinPairFollow` 给出对脚落点，`bindRole` 在
   **同一次提交**里写两个 key；判据求值把「对脚跟得上」也算成立（其余谓词一字不让）。
2. 显式「整对搬」按钮/右键动作：**不做**（形状 1 已覆盖；多一个入口 = 多一处要维护的判据）。
3. 谓词层面 `follows` + 建议落点：**不做**（要动 `/api/bindings/matrix` 契约；前端
   `pinPairFollow` 用现有 `constraint.instances` + `pair` + 板定义就算得出同样的落点）。

## 交付（实现后的实际形状）

- `fx/pin-model.js`：新增 **`pinPairFollow(model, board, roleKey, pin, bindings)`**——
  「点这一脚时对脚该写到哪」。返回三种：
  - `{same: true, mate, at}`：对脚**原地不动**就成立 → 只写本脚；
  - `{same: false, mate, from, to, bound}`：对脚跟到 `to`（`from = null` / `bound = false`
    = 对脚未绑、走默认脚）；
  - `null`：没有对脚 / 这对此刻搬不动 → 照旧灰显（诚实，不制造中间非法态）。
  落点规则（确定、可复述）：对脚 `selectable` 里满足 ①与本脚同实例（pwm 按通道过滤后比
  **基名**、uart/i2c 按实例名**精确**比）②对脚**自己的其它**谓词放行（槽位互斥 / 端口组
  照常求值——对脚跟过去也不许踩坏别的门禁）③未被别的角色占用（被占 = 让位，沿用
  `bindRole` 既有的「替换占用者」语义）的脚；其中**优先「与本脚同一份实例集」的那只**
  （板上成对脚彼此同实例集），同级内取后端 `selectable` 序首个。
- `pinModelVerdict` / `pinModelMissReason` 加可选第 5 参 `bindings`（当前观测绑定）：
  谓词里**只有**成对实例那一条不成立、且 `pinPairFollow` 给得出落点时视为成立
  （其余谓词 / 多条并存里的其它条一字不让）。不传 `bindings` 时前端按 `{}` 算
  （= 全默认观测），既有调用点行为不变。
- `ui/generate-pins.js`：`bindRole` 改为**两脚一次提交**——先按落点让出占用者
  （`freePin`，与原「替换本脚占用者」同一语义），再写两个 key，然后**一次**渲染 +
  `syncStep7`（不再中间渲染，避免闪出半搬态）；`pinCanHost` / `pinMissReason` 把
  `pinBindings` 作为观测传进模型（跟随落点取决于对脚此刻在哪、谁占着脚）。
  成对搬时给一条提示条：「…是成对外设脚，已**成对搬**：`<TX> → PA28`、`<RX> → PA31`
  （同一实例，缺一必被后端拒）」。
- 判据本体**一字未动**：`resolve_bindings` / `_check_paired_role_instances` /
  `/api/bindings/validate|auto|matrix` 的请求响应形状与文案全不变（本单纯前端交互）。

## 验收（全部达成）

- [x] mspm0 上把 `debug_uart` 对从 UART2 搬到 UART0 在界面上**一次点击**走通：点
      `debug_uart.DEBUG_UART_TX → PA0`（UART0）时同一份提交写成
      `{TX: PA0, RX: PA1}`，后端收；再点回默认 `PA23`（UART2）时对脚跟回 UART2 的
      RX 脚，同样收。证据：`test_paired_move_round_trip_from_default_seed`
      （两次点击都用**前端镜像**算出的 bindings，每步整份回验 `resolve_bindings`）。
- [x] 反向：**不允许**任何交互把成对角色写成分属两实例——对脚落点被别的角色占满时
      模型当场挡住（`_frontend_pair_follow` → `None`），旧交互唯一能走的那一步
      （只写本脚 `{TX: PA0}`）后端仍拒（用例钉住「后端判据没被动」）。
      此外**后端 400 的文案不再出现在用户路径上**：真机审计 P 节 UI 说行 617 条逐条
      回验后端全收、UI 说不行的 127 条后端全部一致拒（FAIL 0 / WARN 0）。
- [x] `tests/js/pin-model.test.mjs` 24 条（+7 成对跟随用例）；`tests/js/*.test.mjs`
      1526 passed（工单 04 时 1519）；`tests/test_bindings_matrix.py` 34 条（+4）；
      `python -m pytest -q` = **4195 passed**。
- [x] 真机走查 `node tests/browser/gen-chain-audit.mjs P`：**FAIL 0 / WARN 0 / PASS 15**，
      产物 `.scratch/gen-chain-audit/audit-P-paired-move.txt`。
      备注（审计自查，防「打勾失信」）：`audit-P-after.txt` 是工单 04 那一轮的产物，本单
      **不覆盖**它（它记录的是当时的 586/158 与单绑定对照口径）；本单的产物是
      `audit-P-paired-move.txt`（617/127 + 一次点击的整份 bindings 口径）。
- [x] 反向验证（`.scratch/mspm0-slot-conflict/reverse_paired_move.py` → 证据
      `reverse-verify-paired-move.txt`）：停用前端「对脚跟随」→ 本单四条新用例
      **4/4 当场红**（守卫不是空转）。

## 实现期修正（审计抓出来的两处，如实记账）

1. **真机审计的对照口径必须跟着改**（第一轮跑出 `FAIL 1 条：31 条 UI 放行但后端拒`，
   例 `motor.PWMAB_C0 → PA0`）：本节原来按**单绑定**回验（`{key: pin}`），而工单 05 之后
   界面一次点击 = **两脚一次提交**——`C0 → PA0` 单看后端拒，界面上点它实际写的是
   `{C0: PA0, C1: PA1}`（同 `TIMA0` 实例的两通道），后端**收**。判据改成「这一下点击写出的
   **整份** bindings」（每个候选独立构造，不做跨候选累积——累积模拟会把每个角色的隐式
   默认脚也算成显式条目，引入与「一次点击」无关的槽位/端口组纠缠）。改完 FAIL 0；
   UI 说行从 586 升到 617、说不行从 158 降到 127（那 31 条就是被放开的成对搬）。
2. **前端镜像的落点偏好要一起镜像**：`_frontend_pair_follow`（Python 对拍镜像）第一版
   漏了「优先同一份实例集」的偏好，于是它选 `PB18`（板序更早的 UART2 RX 脚）而前端选
   `PA22`（与候选脚 PA23 同实例集）——对拍不红（都合法）但用例断言当场红，说明**偏好
   也是口径的一部分**，镜像必须逐条对应。

## 不做 / 记账

- 不动 `resolve_bindings` / `_check_paired_role_instances` 的判据（工单 04 已与模型对齐）。
- 不做「整组 slot 批量搬」（工单 03 起就明确不做，仍是一脚一脚）。
- 不做显式「整对搬」按钮 / 谓词层 `follows` 字段（见「拍板与形状」）。
- **全库默认脚铺满时对脚无处可落**（实测，不是缝）：种子 = 全库每个角色显式绑回默认脚时，
  对脚的候选落点全被别角色的默认脚占着（UART2 的 RX 脚 PA24 被 `pid.GRAY_D1` 默认占、
  UART3 的 PB3 被 `as32` 默认占、UART1 的 PA18 被 zigbee 默认占）→ 跟随恒 `None`，
  一个可搬的脚都不给。这是「全库默认铺满」的静态事实（后端那一份绑定确实搬不动），
  真机上用户是**选了几个模块**再配脚，故用例只用 `debug_uart`。要根治得先有「让位重排」
  交互（属 pin-auto-assign 的面），不在本单。
- `pinPairFollow` 的落点是**算法确定性**结果（不是用户指定）：用户想让对脚落别的脚时，
  再点一次对脚即可（成对脚会一起跟），提示条里写明了这条。
