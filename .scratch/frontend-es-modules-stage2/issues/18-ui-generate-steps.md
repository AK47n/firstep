# 18 — 生成页 · 步骤导航 + 草稿 + 总览 + 卡折叠：static/js/ui/generate-steps.js

**要做什么：** generate tab 的「步骤导航（mark/unmark/sync）/ 草稿保存恢复 / 生成总览（overview）/ 卡折叠（initCardCollapse）」簇迁入 `static/js/ui/generate-steps.js`；**stepDoneSet 拥有者**；restoreDraft 内 chosenPlatform 赋值改调 `setChosenPlatform`（工单 12 导出）。**被谁阻塞：** 02 + 12（setChosenPlatform / renderSelected / renderWarnings）

**状态：** 已实施（resolved）

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数/常量（8326-8669 + 8823-8875）：STEP_NAV_CARD_SELECTOR 8326 / stepCard 8328 / markStepDone 8336 / markStepUndone 8347 / unmarkSteps 8358 / syncStep7 8362 / IIFE initStepNav 8376 / DRAFT_KEY 8427 / collectDraftState 8430 / scheduleDraftSave 8438 / clearDraft 8442 / restoreDraft 8446（**改 setChosenPlatform**）/ stepDoneSet 8483 / STEP_TOTAL 8482 / syncStepDone 8485 / renderStepProgress 8491 / overviewPlanNow 8514 / genOverviewWarn 8526 / refreshGenOverview 8530 / runOverviewFill 8595 / initGenOverview 8620 / CARD_COLLAPSE_SELECTOR 8823 / initCardCollapse 8825。
- 依赖：`$`（app.js）；fx 域件：fx/draft.js（draftState / draftSave / draftLoad / draftRestoreMeta / stepProgress / stepNav* / step7DoneState / syncStep4）+ fx/overview.js（genOverviewChipsHTML / overviewFillPlan / overviewReadyToGenerate / cardStepStatusHTML / hasWarnContent）+ fx/generate.js（syncCollapseBtn / collapseToggleAll / collapseBtnLabel）；A 簇（renderPlatforms / renderSelected / renderWarnings + setChosenPlatform —— import 自 ui/generate-recommend.js）。
- 跨簇读方：readinessState@8746 `stepDoneSet.has(5)`（RD 簇，工单 19 import 本模块）；页签分发器 @2321 `stepDoneSet.size==0`（host import stepDoneSet 读）。
- 结构钉：step-done-refs.test.mjs（markStepDone(2) / syncStep4( 调用点 → 本文件；stub「syncStep4(); 计数」→本文件 import）。

## 检查表

- [x] 新建 `static/js/ui/generate-steps.js`：上述件逐字搬移 + import（app.js / fx/draft.js / fx/overview.js / fx/generate.js / ui/generate-recommend.js）+ export（stepDoneSet / STEP_TOTAL / markStepDone / markStepUndone / unmarkSteps / syncStep7 / syncStepDone / initStepNav / initGenOverview / refreshGenOverview / restoreDraft / collectDraftState / clearDraft / initCardCollapse / renderStepProgress）+ 头部注释（stepDoneSet 所有权 + 读方清单）
- [x] index.html：CRLF 感知行区间删除（8326-8669 内目标名 + 8823-8875 CARD_COLLAPSE 块；**物理升序**）+ 顶部 import 行追加
- [x] restoreDraft 改 `setChosenPlatform(d.platform)`；主体中若残留 `chosenPlatform =` 写点（全簇审计）改 setter
- [x] 结构钉重指向：step-done-refs.test.mjs → 本文件
- [x] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 步骤/总览实况（markStepDone 一次 + 草稿恢复）
- [x] grep 零残留：index.html 无 `function markStepDone(` / `const stepDoneSet` 等定义
- [x] 中文提交

## 实施记录（工单 18）

### 清单校正（issue 与 spec cut 方案有出入，以 grep 复核为准）
- **issue 函数清单大多已随工单 12 迁 ui/step-state.js**（STEP_NAV_CARD_SELECTOR / stepCard / markStepDone / markStepUndone / unmarkSteps / syncStep7 / initStepNav IIFE / stepDoneSet / STEP_TOTAL / syncStepDone / renderStepProgress / CARD_COLLAPSE_SELECTOR / initCardCollapse——host import 行 2243 已引用）。本单实际迁移体 = **草稿段（2592-2646）+ 就绪总览段（2653-2814）**：DRAFT_KEY / DRAFT_FIELDS / collectDraftState / draftTimer / scheduleDraftSave / clearDraft / restoreDraft + 清除按钮×2 / 4 输入顶层监听；GEN_CRITICAL_STEPS / GEN_RECOMMENDED_STEPS / genOverviewTitles / genOverviewBadges / overviewPlanNow / genOverviewWarn / refreshGenOverview / FOCUS_TARGETS / runOverviewFill / initGenOverview（scroll/resize/操作区监听在 init 内）。
- **stepDoneSet 拥有者 = step-state.js（12）**——本单无所有权变更（issue「stepDoneSet 拥有者」已随 12 落地）。
- **restoreDraft 的 chosenPlatform 写点工单 12 已改 setChosenPlatform**——`chosenPlatform =` 全簇 grep 零残留，本单无需 setter 改造（issue 检查表该项提前完成）。
- **step-done-refs.test.mjs 已于 12 重指向 generate-recommend.js**（文件头注明「cut 方案复核后非 generate-steps」）→ 本单不改。
- 卡折叠块（8823-8875）已随 12 迁 step-state；设置页折叠已随 10 迁 settings。

### 关键决策
- **readinessState 接缝**：refreshGenOverview（2739 原文）调用 host 内联 readinessState（readiness 簇，工单 19 迁）→ 本单建 `setStepsDeps({ readinessState })` 接缝（与 15→16 的 setGenerateCoreDeps 同构；19 迁出后改静态 import——届时 steps→readiness 与 readiness→step-state（12）无环）。
- **host 无 A↔steps 环**：A 簇对 scheduleDraftSave 的调用继续经 host 注册的 setClusterDeps 闭包（2918 注记「工单 18 迁」→ 已迁，注册行保持）；steps 单向 import A（setter + render 函数 + lastRecommend/selectedSlugs/chosenPlatform 状态读）。
- **模块依赖补漏（diag 抓出）**：collectDraftState 使用 chosenPlatform——apply-18 初版 import 清单漏该名（24-25 行重写后补入）；`export function setStepsDeps` + 尾部导出清单 = **第三次 Duplicate export**（15/16 教训重犯）→ 改纯声明。教训：新模块一律纯声明 + 尾部清单，且每迁出一个小簇都要「依赖名 vs import 清单」比对。
- 模块 265 行；index.html 2976→2779（-197）。

### 验证矩阵（全绿）
- node --test：444/444；pytest：2465 passed（后台任务 pwsh-20）；diag 零 EXC；smoke 11/11。
- probe-18.mjs：9/9（动态 import / 总览 chips=12 渲染 / markStepDone(1) → chip done 态 + 进度条「已完成 1/12」/ 草稿防抖落盘 / reload 恢复 + draft-tip / 清除按钮文案翻转 / 全程零 EXC）。
- grep 零残留：13 名（草稿 5 + 总览 8）在 index.html 无定义；scrip 启动区调用（restoreDraft@末位 / initGenOverview / setStepsDeps 注册）与 setOnStepChange 联动回调保持。

## 风险点

- stepDoneSet 是 `let`/`Set`——`import { stepDoneSet }` 后读 OK；**不得整换**（若重新赋值，改方法调用如 `stepDoneSet.clear()`）。
- initStepNav IIFE（8376-8426）在模块顶部执行（import 时机）——DOM ready 由 module defer 保证，冒烟验证。
- card-collapse 测试（tests/js/card-collapse.test.mjs）已 import fx/generate.js——本票后其「设置页折叠块从 index.html 抽取」部分（settings-collapse.test.mjs）由工单 10 已迁——核对无残留抽取。
