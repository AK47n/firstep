# 09 — 修：`/api/selection/expand` 失败时无退路自激重试（按钮永久禁用、报错被自己清掉）

**要做什么：** 展开请求失败（500 / 超时 / 断网）时，界面必须**停下来**——按钮恢复可点、
错误原因留在界面上、不再自动重打请求；用户手动再点才重试。

**被谁阻塞：** 07（`runExpand` 的收尾重跑是 07 引入的，本次是它的失败路径缺口）。

**状态：** resolved

- [x] 真机复现（现成）：深挖脚本 **D 节**（`/api/selection/expand` 恒 500）：修前实测
      `3s 内 32 次 → 再 3s 共 63 次（≈10.5 次/秒）`，且 `btn-expand` **一直 disabled**、
      `#expand-msg` 恒为**空串**。
- [x] 根因已定位：`runExpand()` 的收尾把两种语义并成了一个条件 ——
      `if ((expandPending || !ok) && …) void runExpand();`：`!ok` 同时覆盖
      「结果被作废」（重跑**对**）与「请求失败」（重跑 = 同参数立刻再打，自激）。
      次生伤害三处：`expandBegin` 每次清空 `expand-msg`（报错被自己擦掉）、
      `expandBusy` 恒 true（按钮永久禁用）、`expandBtnLabel` 已还原（界面看起来没坏）。
- [x] **修法（判据上移到 fx 层，单一来源）**：新增纯函数
      `expandOutcomeDecision(outcome, ctx)`（`static/js/fx/recommend.js`），把三种结局的
      后续动作分开：
      | 结局 | retry | keepError | 语义 |
      |------|-------|-----------|------|
      | `applied` | 仅 `pending` 时 | false | 结果已落地；在途期间被触发过才补跑一次 |
      | `discarded` | ✅（缺平台 / 空选择集除外） | false | 令牌 / 快照拦下 = 结果配不上现在的选择集，**必须**重跑（工单 07 收敛口径） |
      | `failed` | ❌ **绝不** | ✅ | 请求失败 = 停下、把原因摊在界面上，由用户决定再点 |
      `ui/generate-recommend.js` 的 `runExpand` 只负责「执行决策」：写 msg、
      `expandEnd()`（恢复按钮可点）、按 `decision.retry` 决定是否 `void runExpand()`。
- [x] 测试守卫：
      * `tests/js/recommend-expand-outcome.test.mjs`（7 条，纯函数）：三结局各自的重跑 /
        报错语义 + 缺平台 / 空选择集不重跑 + **结构守卫**（ui 层不得再出现
        `pending || !ok` 合并重跑）；
      * `tests/browser/module-intro.spec.mjs` 新增真机用例「展开失败：不自动重跑（无自激）、
        按钮可点、失败原因留在界面上」；
      * 旧守卫 `tests/js/module-intro-detail.test.mjs` 里钉实现形状的第 160 行
        （`(expandPending || !ok)`）**按新判据改写**（不是删——它守的是「选择集变化后必须
        重跑」这条口径）。
- [x] **反向验证（本单关键）**：把 `failed` 分支临时改回 `retry: true`，用例当场变红：
      * 真机：`expand 恒失败却打了 312 次请求`（2.5s 内）；
      * 纯函数：`failed 重跑了 → 失败即自激打后台`。
      改回后两侧全绿，确认过的回退痕迹已清除（grep 无 `TEMP 反向验证` 残留）。
- [x] 归零回归（修后实测）：`pytest` **4161 passed**、`node --test "tests/js/*.test.mjs"`
      **1490 passed**、`node --test tests/browser/module-intro.spec.mjs` **8/8**、
      深挖脚本 D 节 **FAIL 0 / WARN 0**（`6s 内 1 次请求`、按钮可点、msg =
      「请求失败（HTTP 500）：内部错误」）。

**没做（如实记录）：** 不加自动重试 / 退避。本仓是本地工具，失败就该让用户看见原因、
自己决定要不要再点；静默重试会把「后端真的坏了」藏起来（这条口径写进了 fx 层注释）。

**同批发现的另两条问题**（不同单，见 `issues/08`、`issues/10` 与
`deep-audit-playwright.md`）：① 点掉 chip 后已选清单**立刻**渲染过期的展开结果（真机
时间线取证）；③ 模块说明弹窗缺全仓既有的弹窗无障碍三件套。这两条**不属于本单**，
本单未动它们的代码。
