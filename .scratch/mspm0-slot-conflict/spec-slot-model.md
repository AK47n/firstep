# 槽位互斥进判据模型 + parity 用例补「累积态」相

## 问题陈述

用户在板图上把某个角色改绑到别的脚，板图显示绿色可绑、点得下去；可一旦同槽位的另一个
角色此刻**也在这份 bindings 里**（哪怕是「显式绑回自己的默认脚」这种 no-op 条目），这一份
提交必被后端 400 拦下，用户在最后一步「生成工程」才看到一句文案。

实测复现（`.scratch/mspm0-slot-conflict/repro_slot_conflict.py`，一条命令、秒级、无浏览器
无 LLM）：

- 单绑定口径：`{huidu.R3: PA0}` → 后端收；
- 累积态口径：`{huidu.R3: PA0, pid.GRAY_D7: PB6}` → 后端拒「共用同一槽位（默认引脚
  PB6）却绑到不同引脚」；
- 而判据模型对 `huidu.R3` 绑 `PA0` 的判定仍是 `selectable 含 PA0 = True / constraint =
  None / 判定 = True`。

`huidu.R3` 与 `pid.GRAY_D7` 默认同为 PB6（八路灰度族刻意重叠），槽位互斥要求两脚同绑
或都不动。

根因是**口径错位**，不是「前端漏了一条 if」：

1. **模型只表达「per-binding 判据」**。端口组（比同组其余角色**当前有效脚**）与 pwm 两
   通道（比对脚**当前有效实例**）天然是「候选脚 vs 累积态」，所以能做进模型；而槽位互斥
   是同一形状的一维（候选绑定 vs 同槽位角色**当前有效脚**），却没有对应谓词。
2. **parity 用例的对照口径比真实提交窄**。`tests/test_bindings_matrix.py` 比的是
   「模型判定 × `resolve_bindings({单个角色: 脚})`」——单绑定；用户点下去时发出去的是
   **整份 bindings**（`collectBindings`）。「单绑定收、累积态拒」这类分歧用例照不出来，
   所以上一轮的守卫全绿而这条 400 通路仍在。`test_greedy_user_walk_…` 虽然走了累积态，
   但只走「每角色贪心取第一个可选脚」单路径，且用的是 P1 审计集（`huidu` 在、`pid` 不在
   → 同槽位对**一对都不在**），同样覆盖不到。

本单是工单 `gen-chain-audit/04` 明确记为「本轮不进」的那条（槽位互斥不做专项渲染），
现在补上，并把用例口径改成真实提交口径。

## 方案

**判据模型新增第四种 constraint 谓词 `slot`（mspm0 专属），与 `_check_slot_conflicts`
同源下发；前端只求值「引脚名相等」。**

响应形状扩展（其余逐字不变）：

```
constraint = null
           | {kind: "port",     port: "B", reason: "…"}
           | {kind: "instance", instances: [...], pair: "<slug>.<role>", reason: "…"}
           | {kind: "slot",     pin: "PB6", peers: ["pid.GRAY_D7"], reason: "…"}
```

谓词语义（口径 = 与后端门禁同源，严格照 `_check_slot_conflicts` + `_mspm0_same_slot`）：

- **同槽位同伴**（判据单源 = 复用 `_mspm0_same_slot`）：同 `default` 脚 **且** syscfg 落点
  同一（`INSTANCES_BY_SLUG` 实例名有交集）的其它角色；`_check_slot_conflicts` 只在
  **被绑定**的角色之间判，故同伴也只在 `bindings` 里出现时才算（未绑角色走默认、不构成
  互斥，后端也不拒）。
- **该组此刻有定解** = 同伴的有效脚（绑定值，缺省默认值）去重后恰有一个 → 候选脚必须等于
  它，否则点下去这一份必 400（`repro` 场景：同伴 `pid.GRAY_D7` 显式在 PB6 → `huidu.R3`
  只能 PB6，`PA0` 灰显 + 后端逐字原因）。
- **有定解的判据**：同伴**全部**未被绑定 → 整组可一起搬到任意脚（不是约束，回 `null`）；
  同伴绑在**不同**脚（观测自相矛盾）→ 该组此刻无解，回 `null` 不假红（与端口组
  `len(ports) != 1 → None` 同一取舍：宁可让用户走到 400 文案，也不把脚全灰掉）。

**parity 用例补「累积态」相**：判据从「模型判定 × 单绑定 resolve」升级为
「模型放行的一步改绑 → 并入累积 bindings → 整份回验后端必须收」。初始累积态包含
「显式绑回自己默认脚」的条目（这正是 `repro` ② 的真实形态，且是既有政策明确允许的载荷
形态——`resolve_bindings` 文档串：「绑定值 == 默认值的条目保留在清单里」）。

## 用户故事

- 作为用户，我把 `huidu.R3` 改绑到 `PA0` 时，如果同槽位的 `pid.GRAY_D7` 这份里还在
  `PB6`，板图必须**灰显 + 一句中文原因**，而不是让我走到最后一步才被 400 拦下。
- 作为用户，`pid.GRAY_D7` 与 `huidu.R3` 都还是默认时，我仍能**把整组一起搬到别的脚**
  （先改一个、再改另一个）——模型不得把第一步就灰掉。
- 作为维护者，我**不想**在 `pinCanHost` 里抄一遍槽位规则；后端以后改 `_check_slot_conflicts`，
  板图自动跟上。
- 作为维护者，我要的是「用例口径 = 真实提交口径」：凡模型放行的一步改绑，整份 bindings
  回验后端必须收；这条守卫将来能自动抓住同型的第四条、第五条门禁。

## 实现决策

- **后端**（`pin_bindings.py`）：`build_bindings_matrix` 在端口组/成对两级之后补第三级
  `slot` 判据；同伴分组复用 `_mspm0_same_slot`（**不复制规则**——它是 `_check_slot_conflicts`
  的判据本体）；分组入口抽一个「角色 → 同槽位同伴」的索引函数（照 `_port_group_roles`
  先例：只回组、不抛错），供模型用。**mspm0 专属**（`resolve_bindings` 只在 mspm0 分支调
  `_check_slot_conflicts`；stm32 各角色宏族独立，加谓词就是假红）。
- **谓词优先级**：端口组 → 成对实例 → 槽位（沿用既有两级顺序，槽位作第三级；
  平级合并会放大「无解 → 不假红」的松弛面，且这三条真同时成立时顺序无关结论）。
- **前端**（`static/js/fx/pin-model.js`）：`pinModelVerdict` 加 `slot` 分支 = 引脚名相等；
  `pinModelMissReason` 天然复用 `constraint.reason`（无需改）。未识别 kind 仍保守放行。
- **不改** `resolve_bindings` / `/api/bindings/validate` / `/api/bindings/auto` /
  `/api/generate` 的请求与响应形状与文案。
- `generate-pins.js` 的 `pinCanHost` 保持「查模型」不往回加规则（工单 05 已收口）。

## 测试决策

三条缝，都是既有最高缝：

1. **后端模型契约**（`tests/test_bindings_matrix.py`）：`slot` 谓词的形状与语义——同槽位对
   （`huidu.R3` × `pid.GRAY_D7` 默认 PB6）在同伴被观测绑定后给出 `{kind:"slot", pin:"PB6"}`；
   同伴未绑 → `null`（整组可搬）；同伴绑在相矛盾脚 → `null`（无解不假红）；mspm0 专属
   （stm32 不给 slot 谓词）。
2. **前端求值**（`tests/js/pin-model.test.mjs`）：`pinModelVerdict` 的 `slot` 分支
   （命中/不命中/无模型降级）；`pinModelMissReason` 逐字回后端 reason。
3. **累积态对拍（本轮的关键缝）**：模型放行的一步改绑并入累积 bindings 后，整份回验
   `resolve_bindings` 必须收（**假绿 = 0**）；同时反向钉假红（后端收而模型挡 = 0）。
   初始累积态 = P1 审计集 + `["huidu","pid"]` 场景下的「显式绑回默认脚」种子。
   既有单绑定对拍（全脚枚举 / 744 / 115 / 158 锚）**保留不动**（它钉的是另一条口径）。

**既有先例**：`tests/test_bindings_matrix.py` 的 `test_matrix_selectable_matches_backend_verdict`
（全脚枚举 × 真 verdict）、`test_greedy_user_walk_…`（累积态回验）；前端
`tests/js/pin-model.test.mjs`；真机 `tests/browser/gen-chain-audit.mjs P`。

## 范围外

- **不开**「全库累积态相」：全库（84 模块 / 176 角色）枚举已暴露另一类既有分歧 188 条
  （`pair` 类：as32 / debug_uart / hc05 / zodbee 族的 UART TX/RX 跨角色成对）——
  那是工单 04 当年**有意**不动的一类（uart 不叠跨角色谓词），与本单的槽位互斥无关，
  且不在用户本轮范围（「别顺手改」）。本单只把它记进完工说明，不在本单修。
- 槽位互斥不做「整组一起搬」的批量交互（仍是一脚一脚绑，第二步走完约束自然解除）。
- 不改槽位门禁本身的判据（`_check_slot_conflicts` / `_mspm0_same_slot` 一字不动）。
- 「组内混端口松弛」显式无解状态 + 守卫（工单 03 附带项）不在本单——用户未点头。

## 补充说明

- 本单不动 `_pwm_channel_suffix` 的下划线锚定（工单 06 的 24 条假绿教训），也不动
  pwm 两脚各自按本脚通道过滤再比基名的口径。
- 复现脚本 `.scratch/mspm0-slot-conflict/repro_slot_conflict.py` 保留：它是「单绑定口径
  vs 累积态口径结论相反」的最小活证据，修好后 ③ 应变成 `判定 = False` 并给出 slot 原因。
