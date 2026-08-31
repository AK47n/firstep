# 01 — Markdown 渲染纯件

**要做什么：** 新增前端 Markdown 渲染纯函数模块（fx/markdown.js）：把 .md 文本解析成带 1 基行号的块列表，并从同一份块列表投影出「预览 HTML」与「大纲标题清单」两份输出；块级语法覆盖标题/段落/围栏代码块/引用/列表（含任务清单、嵌套）/管道表/水平线，行内覆盖粗体/斜体/行内码/删除线/链接/图片；所有原文先 esc、不透传原始 HTML、URL 协议白名单（javascript:/data:/vbscript:/file: → 文本兜底）；图片 src 经注入的 imageUrl 回调产出（纯件不感知目录与后端端点）。同时：`languageOf` 增 `.md/.markdown → md`（高亮分发对 md 仍回退 plain），代码查看器文件 tab 徽标补「MD」。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `parseMarkdownBlocks` 对标题各层级（含闭井号）、段落软换行、围栏代码块（未闭合兜底到文末）、引用、有序/无序/嵌套列表、任务清单、管道表、水平线产出正确块与 1 基行号。
- [x] `markdownPreviewHTML` 输出 VSCode 式预览 HTML：标题 h1-h6、表格含 thead、代码块 `<pre><code>`（fence 语言经既有高亮单源着色、其余纯文本）、任务清单为禁用 checkbox、引用/列表/hr/svg 图片均有对应结构。
- [x] 行内解析：`code`/粗体/斜体/删除线/链接/图片正确，原文先行转义；`<script>`、`javascript:` URL、属性注入尝试不产生可执行形态（单测断言）。
- [x] `markdownOutline` 从同一块列表投影标题清单（kind=heading、name、line、level），与预览 HTML 的标题结构一致（行号不漂移）。
- [x] 图片 src 经 imageUrl 回调：相对路径/`./` 正常映射，`../` 与绝对/协议路径由回调拒绝（返回空/占位标记），渲染不产生请求。
- [x] `languageOf("a.md")`/`languageOf("a.markdown")` → "md"，其余扩展名行为不变；`highlightText(src,"md")` 仍为纯文本 esc。
- [x] `codeFileTabHTML` 对 md 显示「MD」徽标，非 md 文件徽标不变。
- [x] `node --test tests/js/*.test.mjs` 全绿（新增 tests/js/markdown.test.mjs + highlight/codeview 既有用例补断言）。

## Comments

- 实施（TDD）：先写 tests/js/markdown.test.mjs（块行号/各语法/未闭合围栏/XSS 与 javascript: 拒绝/URL 白名单/imageUrl 回调/大纲投影一致性），红 → 实现 fx/markdown.js（parseMarkdownBlocks / markdownPreviewHTML / markdownOutline + window 桥）→ 绿；highlight.js languageOf 增 md、codeview.js 徽标补 MD、既有测试补断言。node --test tests/js/*.test.mjs 958 项全绿。
- 双轴评审：Standards——2 处导出注释失准（languageOf / codeFileTabHTML 未随 md 分支更新，已修）+ 块起点判定与 isBlockStart 双份正则（抽 blockStartType 单一口径）+ inline 命名过泛（改 renderInline）；Spec——data-md-line 仅标题（改全部块级元素）、无回调时 ../ 可请求（新增 isSafeImageSrc 纯件防御：../ 跨基准/绝对路径/协议相对/非 http(s) 协议拒绝）、嵌套有序子列表丢 start（renderListItems 补 start 属性）、~~~ 围栏超规格（移除，仅背引号）。整改后 958 项全绿。
