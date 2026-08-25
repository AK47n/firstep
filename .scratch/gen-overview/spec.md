# 生成页就绪总览与卡片状态徽章（gen-overview）

## 问题陈述

生成页有 12 步卡片 + 左侧步骤导航，但用户打开页面时很难一眼看出「我走到哪了、还差哪几步才能生成」。当前状态信息零散：已完成步骤只在左侧导航上打 ✓（窄屏 ≤1179px 时导航整个隐藏，无任何步骤提示）；卡片本身不显示任何状态；「还差什么才能点生成」需要用户自己对照记忆。

## 方案

在生成页顶部加一条**就绪总览条**：12 个步骤 chip（数字/✓ + 短标签），随滚动高亮当前步、随完成变绿 ✓、有警告变黄 ⚠；点击 chip 平滑滚动到对应卡片；下方一行摘要「已就绪 N/12」+「还差：…」（关键路径：题面/平台/模块/生成）+「建议顺带完成：AI 推荐/main.c 骨架」。窄屏时该条是唯一步骤导航。同时给每张步骤卡标题右侧加小状态徽章（已就绪 ✓ 绿 / 有警告 ⚠ 黄 / 当前 ● 青），状态与既有的 stepDoneSet / 步骤导航完全同源。

## 用户故事

1. 作为用户，我打开生成页就能看到 12 步的整体进展和还差哪些关键步骤，以便知道下一步该做什么。
2. 作为用户，我点击总览条上的任意步骤 chip，就能直接滚动到对应卡片，以便省去手动找。
3. 作为用户，我在窄屏（左侧步骤导航隐藏时）仍能通过总览条导航所有步骤。
4. 作为用户，我完成某一步后能同时在该卡标题和总览条上看到 ✓，以便确认状态。
5. 作为用户，我在模块清单有平台警告（第 6 步）或引脚有板载共用警示（第 7 步）时，能在总览条和卡标题看到 ⚠，以便不被「已完成」误导。

## 实现决策

- 只改前端单文件 `src/contest_generator/static/index.html` 与新增 `tests/js/gen-overview.test.mjs`；无后端改动。
- 纯函数按仓库惯例抽取（`genOverviewChipsHTML` / `genOverviewSummaryHTML` / `cardStepStatusHTML` / `hasWarnContent`），供 node:test 直接抽取单测。
- 状态源复用既有 `stepDoneSet`（`markStepDone`/`markStepUndone`/`syncStepDone` 唯一入口）与 `.step-nav .step-dot.current`（滚动当前位置），不新建状态。
- 关键路径常量 `GEN_CRITICAL_STEPS = [1,3,6,9]`（题面/平台/模块/生成——与 btn-generate 前置校验一致）；软建议 `GEN_RECOMMENDED_STEPS = [5,8]`；2 简介 / 4 资料可选，10/11/12 为生成后步骤，不计入关键路径。
- 警告判定：第 6 步看 `#warnings` 内是否有非 `.ok` 子元素（「均可直接用」是绿色 ok 盒不算警告）；第 7 步看 `#pin-warn-list` 同理。
- 总览条结构：`#gen-overview` 容器（面板样式，沿用阴影/边框令牌）+ `.ov-chips`（12 个 `.ov-chip` 按钮）+ `.ov-summary`（摘要行）。chip 标签用 CSS `max-width` 截断，完整标题放 title 属性。
- 卡片徽章：`initGenOverview` 为每张带 `.step-no` 的卡在 h2 内追加 `.card-step-status`（插在折叠按钮之前，`initCardCollapse` 在其后追加不影响顺序）。
- `syncStepDone` 末尾调用 `refreshGenOverview()`，滚动/缩放监听也刷新总览条；与步骤导航共用 120px 阈值语义（通过读取 `.step-dot.current` 拿当前步，避免重复计算与初始化顺序问题）。

## 测试决策

- 沿用 `tests/js/*.test.mjs` 抽取范式（node:test + node:assert）；因被测函数内含 `} else {` 与箭头块，本测试文件改用**花括号配平提取**（naive 的 `[\s\S]*?\n\}` 会在第一个顶格 `}` 截断）。
- 覆盖：chips 渲染（done 打勾/current 高亮/未完成数字/引号转义）、摘要（计数/还差关键路径/软建议/全齐提示/建议完成隐藏）、卡徽章四态、hasWarnContent 的 ok 盒排除。
- 全量 `node --test "tests/js/*.test.mjs"` 保持 182 绿；`tests/test_repo_language.py` 兜底中文。

## 范围外

- A3「一键补齐并生成按钮」、C1 快速模式（题面→AI 推荐→自动展开→自动骨架→生成）等其他优化菜单项。
- 后端生成校验改动；持久化步骤状态；多实例配置卡（无 .step-no，不进总览）。
- B1 成果面板重做、B2 最近生成列表、B3 评分点覆盖清单等结果体验项。

## 补充说明

本轮为用户「先做 1-2 个小改动看效果」的试点：仅实现 A1 总览条 + A2 卡标题徽章。若效果满意，后续轮次再议 A3 / C1 / B 系。
