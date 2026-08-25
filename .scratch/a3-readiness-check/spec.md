# A3 检查能否生成（检查模式）— spec

## 问题陈述

用户点「生成工程」时才被告知缺什么（平台 / 模块 / 题面 / 输出目录），且每次只弹一条错误，要反复试错才能凑齐。需要一个「检查能否生成」入口：点一下看到完整检查单——哪些已就绪、哪些缺、缺的怎么补——并且**不自动执行任何流程**（用户已确认选 ① 检查模式，非 ② 自动补齐）。

## 方案

第 9 步卡（输出目录并生成）「生成工程」按钮旁新增按钮「检查能否生成」（`data-ico="check"`）。点击后在按钮下方展开检查单 `#readiness-check`：

- **硬条件 4 项**（与 btn-generate 前置校验**完全同源**，判据抽成纯函数共用，避免两处漂移）：目标平台(3) / 模块清单(6) / 赛题原文(1) / 输出目录(9)，逐项 `✅ 已就绪` / `❌ 原因` + 「去第 N 步」定位按钮；其中「模块清单」❌ 且题面已填时，多一个「一键跑推荐」（复用 `startRecommend`，与「让 AI 推荐」按钮同一入口，不自动跑其它流程）。
- **软条件 2 项**（不阻断生成，`⚠ 建议` 展示 + 定位按钮）：AI 推荐未跑(5) / main.c 骨架未生成(8)。
- 检查文案（reason）与现 btn-generate 逐字一致，保证「检查结果」与「点了生成被拦的提示」完全对得上。

## 用户故事

- 作为用户，点「检查能否生成」立刻看到全量检查单，不用逐个点按钮试错。
- 作为用户，检查单每一项都能一键跳到对应步骤；缺模块时能一键跑推荐（仍需题面）。
- 作为用户，检查单结论与我点「生成工程」被拦时的提示一致（同源判据，不吵架）。

## 实现决策

1. **纯函数 `generateReadinessChecks(state)`**：`state = { chosenPlatform, selectedSlugs, problem, desktopOutput, outputDir }`（全原始值），返回按原提示顺序 `[3 平台, 6 模块, 1 题面, 9 输出目录]` 的检查项 `{ step, title, reason, ok, autoFixable }`；reason 文案：请先选择目标平台 / 请先选择模块 / 请先填写赛题原文 / 请填写输出目录（逐字复用）。判定逐条对应 index.html 3804-3810：`!chosenPlatform`、`!selectedSlugs.length`、`desktopOutput && !problem`、`!desktopOutput && !outputDir`。仅 `6 模块` 的 `autoFixable: true`。
2. **纯函数 `readinessSoftChecks(state)`**：state 另含 `recommended`（= `stepDoneSet.has(5)`）、`hasMainC`（= `!!$("main-c").value.trim()`）；返回软项 `{ step, title, reason, ok }`：5 AI 推荐模块（reason「建议跑一次 AI 推荐（可选）」）、8 main.c 骨架（reason「骨架未生成（可选，生成时可留空）」）；**5 仅在 selectedSlugs 非空时返回**（模块为空已由硬检查 6 覆盖，避免重复）。
3. **纯函数 `readinessRowHTML(check, opts)`**：渲染单行（状态图标 `✓/✗/⚠` + 标题 + reason + 动作）。`opts.recommendEnabled` 为真且该项 `autoFixable` 且 `!ok` 时才渲染「一键跑推荐」按钮（`data-action="recommend"`）；`!ok` 恒渲染「去第 N 步」（`data-step` 属性）；`ok` 行只显示 `✓ 已就绪` 无动作。`readinessRowsHTML(items)` = join。
4. **btn-generate 改源**：3804-3810 换成 `generateReadinessChecks(readinessState()).filter(c => !c.ok)` 取首个的 reason 提示——文案、顺序、行为逐字节不变（单一事实源，先例：`collectBindings`/pin-verdict-seam/01）。
5. **`readinessState()`**（薄 DOM 读取，不单测）：从页面取 chosenPlatform / selectedSlugs / problem / desktopOutput / outputDir / recommended / hasMainC。
6. **面板渲染 `renderReadinessPanel()`**：`readinessState()` → hard+soft → `readinessRowsHTML` → 写 `#readiness-check` innerHTML；面板隐藏时直接 return（零成本）。事件用容器**事件委托**：`.rc-go` → `stepCard(n).scrollIntoView({behavior:'smooth',block:'start'})`；`.rc-recommend` → 题面非空守卫（空则滚动到第 1 步）、`recommendClarifications = []`、`startRecommend($("problem").value.trim())`（与 2352 按钮同一入口）。
7. **联动刷新**：`syncStepDone` 里的 `refreshGenOverview()` 旁追加 `refreshReadinessPanel()`——推荐完成 → markStepDone(5/6) → 面板自动更新。
8. **A3 按钮**：`#btn-readiness-check`，点击 = 面板 `classList.toggle("hidden")` + `renderReadinessPanel()`；首次点击展开并渲染，再点收起/展开（面板重渲染保持最新）。
9. 按钮与面板的 CSS 复用 `.row`/状态色令牌（`--ok/--warn/--danger`），样式追加在 `.card-step-status` 块之后（index.html ~770 行后）。

## 测试决策

`tests/js/readiness-checks.test.mjs`（node:test + node:assert；抽取用**花括号配平**范式——参照 `tests/js/gen-overview.test.mjs`，旧 naive 正则 `match(/function NAME[\s\S]*?\n\}/)` 遇 `} else {`/顶格 `}` 会截断）：

- `generateReadinessChecks`：全空（desktop 默认）→ [3,6,1] ❌ + 9 ✅；test 覆盖 desktop=false 时题面空 → 1 ✅ 且 9 ❌；全齐 → 全 ✅；返回顺序 [3,6,1,9]；reason 文案逐字断言。
- `readinessSoftChecks`：`recommended=false + slugs 非空` → 含 5；`slugs 空` → 不含 5；`hasMainC=false` → 含 8；`true` → 不含 8。
- `readinessRowHTML`/`readinessRowsHTML`：❌ 行含 `data-step` + 去第 N 步 + reason；✅ 行含「已就绪」且无按钮；`autoFixable + recommendEnabled` → 含「一键跑推荐」；`recommendEnabled=false` → 不含；`ok=true` 即使 autoFixable 也不出自动按钮；软行含 ⚠ 无自动按钮；属性引号转义。
- 抽取后 `new Function` 语法检查（照旧：主 script 块两块）。

## 范围外

- 不自动执行除「一键跑推荐」外的任何流程（自动补齐 / C1 快速模式另立 spec）。
- 不在检查单里调 `/api/bindings/validate` 做深度引脚校验（生成前已调；引脚冲突已有第 7 步 `#pin-warn-list` 警告通道 → 总览 ⚠）。
- 不改第 10 修复中心 / 11 修订与深化 / 12 交接提示词。
- 总览条「还差」文案不动（与检查单同源但展示口径不同，如需统一另立工单）。
