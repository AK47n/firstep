# 03 — 页首总开关「全部收起 / 全部展开」

**要做什么：** 设置页首部加一条工具栏（muted 提示文案 + 「全部收起 / 全部展开」按钮）：一键切换全部折叠元素（8 张卡 + 计费小节）并落盘；按钮标签随全局状态重算——全部折叠时显示「全部展开」，否则显示「全部收起」。

**被谁阻塞：** 02（总开关作用于含计费小节的全集，需 02 先就位）

**状态：** resolved

- [x] `#tab-settings` 首部新增 `.settings-toolbar`：flex 两端对齐，muted 提示「点击卡片标题可折叠/展开，状态自动保存。」+ `<button id="btn-settings-collapse-all">`
- [x] 点击按钮：任一展开 → 全部收起；全部已收起 → 全部展开；对全部 `[data-collapse-id]` 元素（含 ai-billing）生效并写盘
- [x] 标签重算口径：全部折叠时显示「全部展开」，否则「全部收起」；单个卡/小节被手动 toggle 后总开关标签同步重算（不依赖按钮自身 class）
- [x] `node --test tests/js/*.test.mjs` 全绿：settings-collapse.test.mjs 断言 settingsMasterLabel 双向
- [x] CDP 截图：点「全部收起」后 8 卡 + 计费全部折叠且按钮变「全部展开」；刷新后状态保持

## 审查记录（2026-xx，双轴 review 对 e910b1e..工作区 diff）

**Spec 轴**：无缺失、无越界；diff 严格限定在 spec 71-74 与工单 5 条验收内，JS 激活链路由 01 交付已就位且口径一致。两处微瑕：① `.settings-toolbar .muted { margin: 0 }` 冗余规则——**已删**（全局 .muted 无 margin、span 无默认外边距）；② 按钮 `type="button"` 与 spec 字面不符——判定为良性质变（与文件其余 JS 生成按钮一致，防未来 form 内误提交），保留。

**Standards 轴**：无硬性违规；判断项（Speculative Generality：`.settings-toolbar .muted` 死规则）与 Spec 轴同一处，已删。JS 激活路径整体核对通过：按钮 id 与 `$("btn-settings-collapse-all")` 一一对应、初始文案 = `settingsMasterLabel(false)`、toolbar div 无 `data-collapse-id` 不会被误收为折叠项。

**验证**：node --test 175 例全绿；check-03 CDP 全过（9 项全收/全展、标签翻转、落盘、刷新保持、手动 toggle 后标签同步）；全部收起态截图目检通过（8 卡仅标题行、保存设置卡保持可见）。
