# 05 — .md 编辑态 + main.c 联动 + 收尾与全量回归

**要做什么：** 补齐特性边角并收尾：① .md 预览态新增「编辑源码」按钮 →
该 tab 切编辑态（可编辑可保存），「返回预览」保留；大纲点击 / 搜索命中/
文件内查找点 .md（预览态）= 自动切编辑态并跳行（取代原「只读临时源码
态」语义，两态归并到 tab.mdMode）；② 保存 main.c 且当前目录 = 生成
上下文 → 调既有 `refreshMainCDiskState()`（generate-mainc-sync 已 export）
刷新步骤 8 状态行（差异提示立即可见）；「去生成页编辑 main.c」桥保留；
③ 文案：nav title / h2「代码编辑器」/ 空态与 tab 按钮 title 更新；
④ CDP 冒烟补齐 + 全量回归（pytest 全量 + tests/js 全量）；⑤ CHANGELOG
由提交信息自动补录（中文提交信息）。

**被谁阻塞：** 03（保存链路；.md 保存依赖）。

**状态：** resolved

**实现笔记：** .md 编辑态（「编辑源码」按钮 → 可编辑可保存；Ctrl+F/查找命中/搜索命中自动切编辑态——含**未开过的 .md 以 mode="edit" 初始化**（评审整改 a1：原固定 preview 导致搜索命中落预览态无选区）；大纲点击保持预览内跳转（文档导航，spec 补充说明显式记录三入口差异））；md 保存后 outline 前端重算（resp.outline 为 null 不清空标题大纲——预防性修复）；main.c 联动（isMainCPath + isMainCDiskDir 单源谓词（评审整改：与「去生成页编辑 main.c」按钮共用，消除双维护），保存后 refreshMainCDiskState → 步骤 8 状态行差异提示）；文案（h2 代码编辑器 / nav title / 空态）；评审整改：renderPane md 编辑分支与普通分支合并（硬性重复违例）、按钮可见性用 tab.mdMode 直判（消 isMdPreviewActive 二次取活动 tab）、.code-md-edit 独立类名（不复用 .code-back-preview 语义）、注释术语统一「编辑」。测试：node 18 项 + smoke-02 20 / smoke-03 12 / smoke-04 8 / smoke-05 11（含 md 大纲存在钉）全过；全量 pytest 3044 绿。

- [ ] .md 两态：预览态「编辑源码」按钮（仅活动 tab 为 .md 且 mdMode=预览 时可见）；切编辑态后 Ctrl+S 可保存；「返回预览」逻辑随 tab 切换保持正确（每 tab 各自 mdMode）。
- [ ] 跳行联动：预览态下大纲/搜索/文件内查找命中 .md → 自动切编辑态并选中跳行。
- [ ] main.c 联动：保存成功且 `isMainCPath(path) && codeDir === getMainCDiskDir()` → `refreshMainCDiskState()`；不引入循环 import（generate-mainc-sync 已在 codeview.js 引用）。
- [ ] 文案更新：`#tab-code` h2、nav `data-tab="code"` title、中栏空态与只读相关措辞、树/侧栏无改动。
- [ ] smoke-05：.md 编辑态往返、main.c 保存后步骤 8 状态行出现「已加载为编辑内容」类差异提示、文案快照。
- [ ] 全量 pytest + tests/js 全绿；提交信息中文。
