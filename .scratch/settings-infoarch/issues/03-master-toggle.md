# 03 — 页首总开关「全部收起 / 全部展开」

**要做什么：** 设置页首部加一条工具栏（muted 提示文案 + 「全部收起 / 全部展开」按钮）：一键切换全部折叠元素（8 张卡 + 计费小节）并落盘；按钮标签随全局状态重算——全部折叠时显示「全部展开」，否则显示「全部收起」。

**被谁阻塞：** 02（总开关作用于含计费小节的全集，需 02 先就位）

**状态：** ready-for-agent

- [ ] `#tab-settings` 首部新增 `.settings-toolbar`：flex 两端对齐，muted 提示「点击卡片标题可折叠/展开，状态自动保存。」+ `<button id="btn-settings-collapse-all">`
- [ ] 点击按钮：任一展开 → 全部收起；全部已收起 → 全部展开；对全部 `[data-collapse-id]` 元素（含 ai-billing）生效并写盘
- [ ] 标签重算口径：全部折叠时显示「全部展开」，否则「全部收起」；单个卡/小节被手动 toggle 后总开关标签同步重算（不依赖按钮自身 class）
- [ ] `node --test tests/js/*.test.mjs` 全绿：settings-collapse.test.mjs 断言 settingsMasterLabel 双向
- [ ] CDP 截图：点「全部收起」后 8 卡 + 计费全部折叠且按钮变「全部展开」；刷新后状态保持
