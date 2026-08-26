# 10 — 设置与评分域：fx/settings.js + fx/score.js（≈21 函数）

**要做什么：** 设置页折叠 + 评分清单 + 评分点格式化全部被测试纯函数迁出；settings-collapse / score-checklist / score-points-format 测试改为 import；页面零变化。settings-collapse 的「先抽核心块再拼同一 Function 作用域」拼接法在此工单改为跨模块 import。

**被谁阻塞：** 01（core.js）

**状态：** resolved（JS 416 全绿 + 浏览器冒烟 11/11 + diag 零 EXC + 探针 10 通过）

## 实施记录

- fx/score.js：15 函数（formatScorePoints / renderScorePointPanel / scoreChecklistPartLabel / scoreChecklistScoreText / scoreChecklistRefsText / scoreChecklistId / scoreChecklistChecked / scoreChecklistLineText / scoreChecklistKey / scoreChecklistItemsHTML / scoreChecklistProgressHTML / scoreChecklistExportText / scoreChecklistParse / scoreChecklistLoad / scoreChecklistSave）；esc import 自 fx/core.js（仅 renderScorePointPanel 用）；scoreChecklistItemsHTML 保留函数体内局部 esc（null→"" 兜底 ≠ core esc，逐字搬移）；尾部 window 桥。
- fx/settings.js：7 函数（parseSettingsCollapse / settingsDefaultCollapsed / effectiveCollapsed / settingsMasterLabel / sectionCollapseLabel / settingsSectionHead / applySettingsCollapseState）+ 常量 SETTINGS_COLLAPSE_KEY / SETTINGS_DEFAULT_COLLAPSED 随迁并 export；**syncCollapseBtn 不重复搬**——工单 08 已迁 fx/generate.js，applySettingsCollapseState 经 `import { syncCollapseBtn } from "./generate.js"` 跨模块引用（fx 模块间首个跨模块 import）；尾部 window 桥。
- 主体 module 顶部 import 行追加 score.js / settings.js 两行；index.html 删除 22 个定义 + 2 个常量（127 行），三处注释改「已迁至 static/js/fx/*.js（工单 10）」；saveSettingsCollapse / initSettingsCollapse / renderScoreChecklist / scoreChecklistIdsNow / scoreChecklistSyncCurrent / scoreChecklistExportNow / initScoreChecklist 等 DOM 胶水留内联；渲染 + 事件委托注释保留于 index.html。
- 测试改造：score-checklist.test.mjs 提取段整体换 import；score-points-format.test.mjs 两段 match 提取换 import（html 保留——「接线结构」断言仍指 index.html 调用点）；settings-collapse.test.mjs match 拼接法整体换 import（跨模块 syncCollapseBtn 由 settings.js 内部引用，测试文件不再注入）；「firstep.settingsCollapse.v1 必须出现在 index.html」断言改「SETTINGS_COLLAPSE_KEY 常量值必须保持」。
- score-points-format.test.mjs 中 `assert.match(html, /id="rec-score-points"/)` 删除——该 id 随 renderScorePointPanel 迁出 index.html，输出样式契约由面板用例直接断言（不丢守卫）；调用点 `renderScorePointPanel(scorePoints)` 断言保留。
- 验证：node --test 416 全绿；diag.mjs 零 EXC（favicon 404 为既有噪音）；smoke.mjs 11/11；探针 probe-10-settings-score.mjs：window 桥 8 函数 + 存储键为字符串、设置页折叠默认态 ai-billing/libs/toolchain/local-llm/vision = 收起（与默认集一致）、面板/清单 HTML 经主体 module import 正常产出。

- [x] 新建 fx/settings.js：parseSettingsCollapse / settingsDefaultCollapsed / effectiveCollapsed / applySettingsCollapseState / settingsMasterLabel / sectionCollapseLabel（+ 顺迁被 applySettingsCollapseState 引用的 settingsSectionHead）及域内常量 SETTINGS_COLLAPSE_KEY / SETTINGS_DEFAULT_COLLAPSED（export）；syncCollapseBtn 由 fx/generate.js 跨模块 import；尾部 window 桥
- [x] 新建 fx/score.js：formatScorePoints / renderScorePointPanel / scoreChecklistPartLabel / scoreChecklistScoreText / scoreChecklistRefsText / scoreChecklistId / scoreChecklistChecked / scoreChecklistLineText / scoreChecklistKey / scoreChecklistItemsHTML / scoreChecklistProgressHTML / scoreChecklistExportText / scoreChecklistParse / scoreChecklistLoad / scoreChecklistSave；esc 从 fx/core.js import；尾部 window 桥
- [x] index.html 删除上述 22 函数定义 + 2 常量；主体 module 顶部 import 行追加两个模块（01 升级约定：无独立 `<script type="module" src>` 标签，import 链自动加载）
- [x] settings-collapse / score-checklist / score-points-format 三个测试文件改 import（跨模块依赖：syncCollapseBtn 由 settings 模块内部引用 fx/generate.js）
- [x] `node --test "tests/js/*.test.mjs"` 416 全绿；diag 零 EXC；冒烟 11/11（设置页折叠默认态 + 评分清单纯函数经 import 生效经探针验证）

- [ ] 新建 fx/settings.js：parseSettingsCollapse / settingsDefaultCollapsed / effectiveCollapsed / applySettingsCollapseState / syncCollapseBtn / settingsMasterLabel / sectionCollapseLabel 及域内常量；尾部 window 桥
- [ ] 新建 fx/score.js：scoreChecklistPartLabel / scoreChecklistScoreText / scoreChecklistRefsText / scoreChecklistId / scoreChecklistChecked / scoreChecklistLineText / scoreChecklistKey / scoreChecklistItemsHTML / scoreChecklistProgressHTML / scoreChecklistExportText / scoreChecklistParse / scoreChecklistLoad / scoreChecklistSave / formatScorePoints / renderScorePointPanel 及域内常量；尾部 window 桥
- [ ] index.html 删除上述定义；加载两个模块 script
- [ ] 三个测试文件改 import（跨模块依赖：syncCollapseBtn 由 settings 模块提供）
- [ ] `node --test` 全绿；冒烟设置页（折叠）+ 生成页评分清单
