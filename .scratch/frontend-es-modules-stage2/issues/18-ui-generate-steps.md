# 18 — 生成页 · 步骤导航 + 草稿 + 总览 + 卡折叠：static/js/ui/generate-steps.js

**要做什么：** generate tab 的「步骤导航（mark/unmark/sync）/ 草稿保存恢复 / 生成总览（overview）/ 卡折叠（initCardCollapse）」簇迁入 `static/js/ui/generate-steps.js`；**stepDoneSet 拥有者**；restoreDraft 内 chosenPlatform 赋值改调 `setChosenPlatform`（工单 12 导出）。**被谁阻塞：** 02 + 12（setChosenPlatform / renderSelected / renderWarnings）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数/常量（8326-8669 + 8823-8875）：STEP_NAV_CARD_SELECTOR 8326 / stepCard 8328 / markStepDone 8336 / markStepUndone 8347 / unmarkSteps 8358 / syncStep7 8362 / IIFE initStepNav 8376 / DRAFT_KEY 8427 / collectDraftState 8430 / scheduleDraftSave 8438 / clearDraft 8442 / restoreDraft 8446（**改 setChosenPlatform**）/ stepDoneSet 8483 / STEP_TOTAL 8482 / syncStepDone 8485 / renderStepProgress 8491 / overviewPlanNow 8514 / genOverviewWarn 8526 / refreshGenOverview 8530 / runOverviewFill 8595 / initGenOverview 8620 / CARD_COLLAPSE_SELECTOR 8823 / initCardCollapse 8825。
- 依赖：`$`（app.js）；fx 域件：fx/draft.js（draftState / draftSave / draftLoad / draftRestoreMeta / stepProgress / stepNav* / step7DoneState / syncStep4）+ fx/overview.js（genOverviewChipsHTML / overviewFillPlan / overviewReadyToGenerate / cardStepStatusHTML / hasWarnContent）+ fx/generate.js（syncCollapseBtn / collapseToggleAll / collapseBtnLabel）；A 簇（renderPlatforms / renderSelected / renderWarnings + setChosenPlatform —— import 自 ui/generate-recommend.js）。
- 跨簇读方：readinessState@8746 `stepDoneSet.has(5)`（RD 簇，工单 19 import 本模块）；页签分发器 @2321 `stepDoneSet.size==0`（host import stepDoneSet 读）。
- 结构钉：step-done-refs.test.mjs（markStepDone(2) / syncStep4( 调用点 → 本文件；stub「syncStep4(); 计数」→本文件 import）。

## 检查表

- [ ] 新建 `static/js/ui/generate-steps.js`：上述件逐字搬移 + import（app.js / fx/draft.js / fx/overview.js / fx/generate.js / ui/generate-recommend.js）+ export（stepDoneSet / STEP_TOTAL / markStepDone / markStepUndone / unmarkSteps / syncStep7 / syncStepDone / initStepNav / initGenOverview / refreshGenOverview / restoreDraft / collectDraftState / clearDraft / initCardCollapse / renderStepProgress）+ 头部注释（stepDoneSet 所有权 + 读方清单）
- [ ] index.html：CRLF 感知行区间删除（8326-8669 内目标名 + 8823-8875 CARD_COLLAPSE 块；**物理升序**）+ 顶部 import 行追加
- [ ] restoreDraft 改 `setChosenPlatform(d.platform)`；主体中若残留 `chosenPlatform =` 写点（全簇审计）改 setter
- [ ] 结构钉重指向：step-done-refs.test.mjs → 本文件
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 步骤/总览实况（markStepDone 一次 + 草稿恢复）
- [ ] grep 零残留：index.html 无 `function markStepDone(` / `const stepDoneSet` 等定义
- [ ] 中文提交

## 风险点

- stepDoneSet 是 `let`/`Set`——`import { stepDoneSet }` 后读 OK；**不得整换**（若重新赋值，改方法调用如 `stepDoneSet.clear()`）。
- initStepNav IIFE（8376-8426）在模块顶部执行（import 时机）——DOM ready 由 module defer 保证，冒烟验证。
- card-collapse 测试（tests/js/card-collapse.test.mjs）已 import fx/generate.js——本票后其「设置页折叠块从 index.html 抽取」部分（settings-collapse.test.mjs）由工单 10 已迁——核对无残留抽取。
