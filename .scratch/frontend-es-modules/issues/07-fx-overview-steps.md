# 07 — 生成概览与步骤域：fx/overview.js + fx/draft.js（16 函数）

**要做什么：** 生成页的概览卡 / 步骤导航 / 步骤状态 / 草稿保存恢复全部被测试纯函数迁出，gen-overview / gen-overview-act / step-nav / step7-done / draft-memory / step-done-refs / step-progress 测试改为 import；页面零变化。

**被谁阻塞：** 01（core.js）

**状态：** resolved（2026-08-26；JS 416 全绿 + 浏览器冒烟 11/11）

## 实施记录

- 数字修正：工单标题「≈18」，实际迁移 = 16 个纯函数。
- 新建 **fx/overview.js**（6 函数）：genOverviewChipsHTML / genOverviewSummaryHTML / overviewFillPlan / overviewReadyToGenerate / cardStepStatusHTML / hasWarnContent；无共享件依赖（GEN_CRITICAL_STEPS / GEN_RECOMMENDED_STEPS 常量由胶水层 refreshGenOverview 使用，留内联作实参传入）。
- 新建 **fx/draft.js**（10 函数）：stepNavTitles / stepNavItemsHTML / stepNavCurrent / draftState / draftSave / draftLoad / draftRestoreMeta / stepProgress / step7DoneState / syncStep4；无共享件依赖（DRAFT_KEY / STEP_TOTAL / STEP_NAV_CARD_SELECTOR 由胶水层使用，留内联）。
- **syncStep4 参数化**（同 06 多实例先例）：原引用主体脚本模块级状态 selectedReferenceIds / autoReferenceIds 并调 markStepDone / markStepUndone（step-done-refs 测试经 Function 注入），迁入后签名 syncStep4(selectedReferenceIds, autoReferenceIds, markStepDone, markStepUndone)——行为零变化；index.html 两处调用点（勾选变更 / 推荐自动关联）同步传参；测试从「new Function 注入」改为直调（runSyncStep4(manual, auto)）。
- index.html：主体 module 顶部 import 行追加两行（module.js 之后）；7 处 CRLF 感知行区间删除（D1 6 行 syncStep4 / D2 24 行 stepNav 三函数 / D3 8 行 step7DoneState / D4 34 行 draft 四函数 / D5 7 行 stepProgress / D6 56 行 overview 四函数 / D7 13 行 cardStepStatusHTML+hasWarnContent），内容锚定 + span 校验通过，替换为「已迁至 static/js/fx/…（工单 07）」注释；胶水留内联：stepCard / attachCelebrate（celebrate.test.mjs 仍从 index.html 提取——不在本工单测试清单）/ markStepDone / markStepUndone / unmarkSteps / syncStep7 / initStepNav / collectDraftState / scheduleDraftSave / clearDraft / restoreDraft / syncStepDone / renderStepProgress / overviewPlanNow / genOverviewWarn / refreshGenOverview。
- 教训：本域多个函数块下一条函数无空行，删除脚本 end 锚点原先只认「} + 空行 + 锚」——改为「} + (空行+锚 | 直接锚)」双形态后全过（首跑在 D7 throw，文件未写坏）。
- 测试改造（7 文件）：gen-overview / gen-overview-act / step-nav / step7-done / draft-memory / step-progress 整头换 import（fs/html/extract 全删——html 仅抽取用）；step-done-refs 保留 html 读入（markStepDone(2) / syncStep4 调用点静态断言），提取工厂换 import，「syncStep4();」计数断言改为「syncStep4(」计数（≥2）。
- 验证：`node --test "tests/js/*.test.mjs"` 416 全绿；diag.mjs 零 EXC（favicon 404 既有噪音）；smoke.mjs 11/11；grep 零残留（16 名无 `function <name>(` 定义）。

- [x] 新建 fx/overview.js：genOverviewChipsHTML / genOverviewSummaryHTML / cardStepStatusHTML / hasWarnContent / overviewFillPlan / overviewReadyToGenerate 及域内常量；尾部 window 桥
- [x] 新建 fx/draft.js：draftState / draftSave / draftLoad / draftRestoreMeta / stepNavTitles / stepNavItemsHTML / stepNavCurrent / stepProgress / step7DoneState / syncStep4 及域内常量；尾部 window 桥
- [x] index.html 删除上述定义；加载两个模块 script
- [x] gen-overview / gen-overview-act / step-nav / step7-done / draft-memory / step-done-refs / step-progress 测试改 import
- [x] `node --test` 全绿；冒烟生成页（概览卡 + 步骤）
