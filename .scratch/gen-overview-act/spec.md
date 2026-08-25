# 就绪总览条行动化：一键补齐 + 就绪生成按钮（A3）

## 问题陈述

生成页顶部已有就绪总览条（#gen-overview，工单 gen-overview/01）：12 步 chips + 「已就绪 N/12 · 还差：…」摘要，但摘要只是文字提示——「还差：赛题原文、目标平台、模块清单…（点上方 chips 直达）」要用户自己一个个点、一个个填。卡 9 的「检查能否生成」面板虽然已有「去第 N 步」+「一键跑推荐」，但要先点开检查按钮才知道缺什么。

## 方案（半自动，已与用户确认）

1. 总览条摘要下方加行动区 `.ov-actions`：
   - **「一键补齐」按钮**：关键路径（1 题面 / 3 平台 / 6 模块；9 是行动本身不列入）缺失时显示；点击后按 1→3→6 顺序依次滚动到对应卡片 + 临时高亮（.ov-fill-target 1.6s 自清），并执行半自动动作：
     - 步骤 1：聚焦 #problem（题面只能用户填/上传，无法自动）。
     - 步骤 3：仅滚动+高亮平台卡——平台选择后果大，不自动选。
     - 步骤 6：若已有 AI 推荐结果（lastRecommend.modules 非空）且模块清单为空 → 自动采用（renderRecommendResult(lastRecommend, true)，可回退：采用后仍可在清单增删）；无推荐结果 → 仅滚动+高亮（用户可走「让 AI 推荐」/检查面板「一键跑推荐」）。
   - **扩规（用户已确认）**：手动输出模式且输出目录为空时，「一键补齐」在 1→3→6 之后追加步骤 9 的 focus-dir 动作（滚到第 9 步并聚焦 #output-dir，不代填）——否则出现「一键补齐」与「生成」按钮都隐藏、仅剩摘要文字指路的死角。桌面模式（默认勾选）不触发。
   - **「生成」按钮**（仅就绪时显示）：就绪判定 = generateReadinessChecks(readinessState()) 全 ok（与 btn-generate 前置校验同源，工单 a3-readiness-check/01 既存）；点击 = `$("btn-generate").click()`；btn-generate 生成中 disabled 时同步禁用。
2. 纯函数（node:test 可直抽直测）：
   - `overviewFillPlan(doneSet, canAdopt, outputDirMissing)` → `[{n, action}]` 按序；action ∈ focus/spotlight/adopt/focus-dir；canAdopt = 有推荐且清单空（显式判定）。
   - `overviewReadyToGenerate(checks)` → 全 ok。
3. 状态同步：refreshGenOverview() 末尾更新两个按钮的显隐/禁用（复用已算好的 doneArr 与 readiness 检查）；两处共用 `overviewPlanNow(doneArr)` 派生计划，避免重复计算。

## 用户故事

- 用户打开生成页贴完题面，发现总览条「还差：目标平台、模块清单」——点一次「一键补齐」，页面自动带我依次走过平台卡、模块卡（有推荐自动采用），最后总览条出现「生成」按钮，直接生成。
- 用户没跑过 AI 推荐：一键补齐走到模块卡高亮，停在原地，不替用户做主。

## 实现决策

1. 复用既存单一事实源：就绪判定不走新逻辑，直接 `generateReadinessChecks(readinessState())`（a3-readiness-check/01-02）；补齐计划只依赖 stepDoneSet + lastRecommend。
2. 自动采用 = `renderRecommendResult(lastRecommend, true)`：它已经处理 autoAdd 去重/多实例回填/评分点/runExpand，且 renderSelected 内部 markStepDone(6)/undone（index.html ~2607）→ syncStepDone → refreshGenOverview 自动联动。
3. 高亮叠加用一次性 class `.ov-fill-target` + setTimeout 移除（对卡片无持久副作用）。
4. 全部前端改动（index.html + tests/js），无后端改动、不需要重启。

## 测试决策

- tests/js/gen-overview-act.test.mjs：overviewFillPlan（全缺/部分缺/全齐/无推荐时 adopt vs spotlight 分支）+ overviewReadyToGenerate（全 ok/有缺）。
- 回归：node --test tests/js/*.test.mjs + headless 冒烟（补齐全流程人工可验）。

## 范围外

- 平台自动选择（全自动模式，用户明确选了半自动）。
- 自动触发生成（生成永远由用户点，含总览条按钮——只是入口聚合）。
- 修改「检查能否生成」面板（保留，两入口并存）。
