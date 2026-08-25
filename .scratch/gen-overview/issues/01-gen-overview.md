# 01 — 生成页顶部就绪总览条（chips + 摘要 + 点击直达）

**要做什么：** 生成页顶部出现一条就绪总览：12 个步骤 chip（数字/✓ + 短标签），当前步青色高亮、已完成变绿 ✓、有警告变黄 ⚠，点击 chip 平滑滚动到对应卡片；下方摘要「已就绪 N/12」+「还差：…（关键路径）」+「建议顺带完成：AI 推荐/main.c 骨架」。窄屏（左侧步骤导航隐藏）时该条兼作唯一步骤导航。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `#gen-overview` 容器插入生成页（draft-tip 之后、gen-layout 之前）
- [x] 纯函数 `genOverviewChipsHTML` / `genOverviewSummaryHTML` 抽取并有单测（chips 状态渲染、摘要计数/还差/建议文案）
- [x] 关键路径常量 GEN_CRITICAL_STEPS=[1,3,6,9]、GEN_RECOMMENDED_STEPS=[5,8]；摘要与 btn-generate 前置校验口径一致（2/4 可选、10/11/12 不算关键）
- [x] chip 点击 → stepCard(n).scrollIntoView；滚动/缩放刷新当前步高亮（读 `.step-nav .step-dot.current`，与步骤导航同源）
- [x] 警告态：第 6 步 #warnings、第 7 步 #pin-warn-list 有非 .ok 内容时 chip 变 ⚠（hasWarnContent 单测覆盖 ok 盒排除）
- [x] `syncStepDone` 联动刷新总览条；`initGenOverview()` 在启动处调用
- [x] 样式沿用主题令牌（--ok/--warn/--accent/-dim、--shadow-card），chip 标签 CSS 截断、完整标题在 title 属性
- [x] 全量 node --test "tests/js/*.test.mjs" 182 绿
