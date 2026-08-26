# 07 — 生成概览与步骤域：fx/overview.js + fx/draft.js（≈18 函数）

**要做什么：** 生成页的概览卡 / 步骤导航 / 步骤状态 / 草稿保存恢复全部被测试纯函数迁出，gen-overview / gen-overview-act / step-nav / step7-done / draft-memory / step-done-refs / step-progress 测试改为 import；页面零变化。

**被谁阻塞：** 01（core.js）

**状态：** ready-for-agent

- [ ] 新建 fx/overview.js：genOverviewChipsHTML / genOverviewSummaryHTML / cardStepStatusHTML / hasWarnContent / overviewFillPlan / overviewReadyToGenerate 及域内常量；尾部 window 桥
- [ ] 新建 fx/draft.js：draftState / draftSave / draftLoad / draftRestoreMeta / stepNavTitles / stepNavItemsHTML / stepNavCurrent / step7DoneState / stepProgress / syncStep4 及域内常量；尾部 window 桥
- [ ] index.html 删除上述定义；加载两个模块 script
- [ ] gen-overview / gen-overview-act / step-nav / step7-done / draft-memory / step-done-refs / step-progress 测试改 import
- [ ] `node --test` 全绿；冒烟生成页（概览卡 + 步骤）
