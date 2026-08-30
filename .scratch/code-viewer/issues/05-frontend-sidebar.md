# 05 — 前端：右侧栏（大纲 + 工程搜索 + 跳转 + 文件内 Ctrl+F）

**要做什么：** 右侧栏两个面板——「大纲」：当前 C 文件函数/宏/include 清单，点击跳到对应行并高亮；「搜索」：输入关键词 → 跨文件结果列表（文件:行号 + 上下文）→ 点击跳转到文件并高亮该行；代码视图内 Ctrl+F 拦截浏览器查找框，走面板内文件内搜索。

**被谁阻塞：** 02、03、04（面板工具有别：02 提供 search 数据、03 提供 outline 数据、04 提供视图容器与跳行基建）。

**状态：** ready-for-agent

- [x] fx/codeview.js 增：`outlineHTML(outline)`（kind 徽标 + name + 行号）/ `outlineEmptyHTML()`（「当前文件无大纲」）/ `searchListHTML(hits, activeFile)` / `fileFindFilter(lineTexts, q)`（当前文件全文客户端过滤，纯函数）；行号 / 高亮渲染复用既有 helper。
- [x] ui/codeview.js：侧栏切换（大纲 / 搜索 tab）；当前文件变化 → 刷新大纲；大纲点击跳行（scrollIntoView + flash 高亮 class）；搜索框提交 → apiGet /api/code/search → 结果列表 → 点击跳文件+行；Ctrl+F 拦截（tab-code 内）→ 文件内搜索面板；空态 / 中文错误 toast。
- [x] tests/js/codeview.test.mjs 扩展（outlineHTML / searchListHTML / fileFindFilter）；既有测试不破；pytest 全绿。
