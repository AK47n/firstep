# 02 — 卡片标题状态徽章（已就绪 / 有警告 / 当前）

**要做什么：** 生成页每张步骤卡标题右侧出现小状态徽章：已完成显示「✓ 已就绪」（绿）、有警告显示「⚠ 有警告」（黄）、当前滚动位置显示「● 当前」（青），其余无状态时隐藏徽章；状态与 stepDoneSet / 步骤导航完全同源，不新建状态。

**被谁阻塞：** 01——就绪总览条（复用其警告判定 genOverviewWarn 与 refreshGenOverview 刷新时机）。

**状态：** resolved

- [x] 纯函数 `cardStepStatusHTML(done, warn, current)` 抽取并有单测（四态：done/warn/current/无状态返回空串）
- [x] initGenOverview 为每张带 .step-no 的卡在 h2 追加 `.card-step-status`（插在折叠按钮前，initCardCollapse 在其后追加，顺序正确）
- [x] refreshGenOverview 内统一刷新徽章 className/textContent；与总览条 chips 同步更新
- [x] 样式 `.card-step-status`（done/warn/current 三态色，沿用 --ok/--warn/--accent 令牌）
- [x] 全量 node --test "tests/js/*.test.mjs" 182 绿
