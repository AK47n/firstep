# 08 — 生成主流程域：fx/generate.js + fx/recent.js + fx/readiness.js（≈21 函数）

**要做什么：** 生成流程（覆盖冲突 / 阶段播报 / 折叠 / 庆祝 / 输出目录 / 结果模块摘要 / 绑定收集 / 价格参考）/ 最近任务 / 就绪检查全部被测试纯函数迁出对应模块；generate-overwrite / stage-report / card-collapse / celebrate / generation-output-dir-payload / format-res-modules / collect-bindings / price-reference-clear / recent-jobs / readiness-checks 测试改为 import；页面零变化。

**被谁阻塞：** 01（core.js）

**状态：** ready-for-agent

- [ ] 新建 fx/generate.js：isConflictError / conflictDirName / genStageTexts / fmtWait / collapseToggleAll / collapseBtnLabel / attachCelebrate / generationOutputDirPayload / formatResModules / collectBindings / renderPriceReference 及域内常量（CONFLICT_MSG_PREFIX 等）；尾部 window 桥
- [ ] 新建 fx/recent.js：recentStatusMeta / recentTimeLabel / recentPlatformLabel / recentStatusNow / recentChipHTML / recentListHTML 及域内常量；尾部 window 桥
- [ ] 新建 fx/readiness.js：generateReadinessChecks / readinessSoftChecks / readinessRowHTML 及域内常量；尾部 window 桥
- [ ] index.html 删除上述定义；加载三个模块 script
- [ ] 对应测试文件改 import
- [ ] `node --test` 全绿；冒烟生成页 + 设置页价格参考
