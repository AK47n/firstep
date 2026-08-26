# 10 — 设置与评分域：fx/settings.js + fx/score.js（≈21 函数）

**要做什么：** 设置页折叠 + 评分清单 + 评分点格式化全部被测试纯函数迁出；settings-collapse / score-checklist / score-points-format 测试改为 import；页面零变化。settings-collapse 的「先抽核心块再拼同一 Function 作用域」拼接法在此工单改为跨模块 import。

**被谁阻塞：** 01（core.js）

**状态：** ready-for-agent

- [ ] 新建 fx/settings.js：parseSettingsCollapse / settingsDefaultCollapsed / effectiveCollapsed / applySettingsCollapseState / syncCollapseBtn / settingsMasterLabel / sectionCollapseLabel 及域内常量；尾部 window 桥
- [ ] 新建 fx/score.js：scoreChecklistPartLabel / scoreChecklistScoreText / scoreChecklistRefsText / scoreChecklistId / scoreChecklistChecked / scoreChecklistLineText / scoreChecklistKey / scoreChecklistItemsHTML / scoreChecklistProgressHTML / scoreChecklistExportText / scoreChecklistParse / scoreChecklistLoad / scoreChecklistSave / formatScorePoints / renderScorePointPanel 及域内常量；尾部 window 桥
- [ ] index.html 删除上述定义；加载两个模块 script
- [ ] 三个测试文件改 import（跨模块依赖：syncCollapseBtn 由 settings 模块提供）
- [ ] `node --test` 全绿；冒烟设置页（折叠）+ 生成页评分清单
