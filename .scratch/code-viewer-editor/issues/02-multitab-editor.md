# 02 — 多标签页 + 可编辑（内存级）：tab 条 + textarea 三明治编辑器

**要做什么：** 「代码」tab 中栏从「单文件只读 pre 视图」升级为 **CCS 式多
标签编辑器（未接保存）**：顶栏标签条（语言徽标 + 文件名 + 脏点 ● + 关闭
×，活动标签高亮，上限 10 个超出中文 toast，打开已开文件 = 激活既有 tab
不重载，关闭脏 tab 弹确认）；编辑层 = textarea 三明治（透明 textarea +
高亮层 + 行号列，三向滚动同步，`--code-zoom` 缩放沿用 Ctrl+滚轮）；Tab =
插入 4 空格（多行选择整段缩进）、Enter = 自动缩进（拷贝前导空白）；光标
行 = 当前行高亮（gutter active）；大纲 / 搜索命中 / 文件内查找点击 = 在
textarea 选中并滚动到该行（复用 fx/code.js `maincLineOffsetRange` 纯函数；
scroll 到选区参数化——不硬编码 #main-c-hl）；非 UTF-8 文件 tab 标
「只读」、无脏点、textarea readonly；现有只读 codeViewHTML 保留作回退。
本票保存不接（脏点 = content !== savedContent 内存级，可演示）。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

- [ ] 新 `fx/codeeditor.js` 纯函数：`codeTabStripHTML(tabs, activePath)`（脏点/只读标记/关闭钮 data-tab-close）、`codeEditorHTML(content, lang, opts)`（三明治，opts.readonly）、`caretLineOf(value, pos)`、`indentLines(value, sel)`/`indentOnEnter(value, sel)`；末尾 Object.assign(window, …) 兼容。
- [ ] 新 `ui/codeeditor.js` 胶水：tab 数组状态（{path, lang, content, savedContent, outline, mtime_ns, utf8, mdMode}）、`openEditorFile(path)`、tab 条/editor 事件委托（激活/关闭/input/scroll/keydown：Tab/Enter/光标行三向同步）、Ctrl+S 占位（本票 toast 提示未接保存或静默，验收以编辑手感为准）。
- [ ] `ui/codeview.js` 改造：树点击 → openEditorFile；大纲/搜索/文件内查找跳行 → 选区跳转；「只读」文案更新。
- [ ] `index.html`/CSS：`.code-tabs` 标签条 + 三明治样式（沿 .code-wrap 机制，font 同源 `calc(13px * var(--code-zoom,1))`）；前端单测 codeeditor.test.mjs（tab 条脏点/只读、caretLineOf、indent、跳行越界）。
- [ ] node --test 全绿；smoke-02 验证：多 tab 开关保留内容、脏点、关闭确认、编辑高亮联动、光标行高亮。

(End of file - total 23 lines)
</content>