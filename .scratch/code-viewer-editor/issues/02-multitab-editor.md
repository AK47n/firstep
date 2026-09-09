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

**状态：** resolved

- [ ] 新 `fx/codeeditor.js` 纯函数：`codeTabStripHTML(tabs, activePath)`（脏点/只读标记/关闭钮 data-tab-close）、`codeEditorHTML(content, lang, opts)`（三明治，opts.readonly）、`caretLineOf(value, pos)`、`indentLines(value, sel)`/`indentOnEnter(value, sel)`；末尾 Object.assign(window, …) 兼容。
- [ ] 新 `ui/codeeditor.js` 胶水：tab 数组状态（{path, lang, content, savedContent, outline, mtime_ns, utf8, mdMode}）、`openEditorFile(path)`、tab 条/editor 事件委托（激活/关闭/input/scroll/keydown：Tab/Enter/光标行三向同步）、Ctrl+S 占位（本票 toast 提示未接保存或静默，验收以编辑手感为准）。
- [ ] `ui/codeview.js` 改造：树点击 → openEditorFile；大纲/搜索/文件内查找跳行 → 选区跳转；「只读」文案更新。
- [ ] `index.html`/CSS：`.code-tabs` 标签条 + 三明治样式（沿 .code-wrap 机制，font 同源 `calc(13px * var(--code-zoom,1))`）；前端单测 codeeditor.test.mjs（tab 条脏点/只读、caretLineOf、indent、跳行越界）。
- [ ] node --test 全绿；smoke-02 验证：多 tab 开关保留内容、脏点、关闭确认、编辑高亮联动、光标行高亮。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点；验收 checkbox 原未勾，代码事实已全部满足）：
  `src/contest_generator/static/js/fx/codeeditor.js`（21179 字节）——
  `codeTabStripHTML`（124，脏点/只读/关闭钮）、`codeEditorHTML`（195，三明治
  textarea+高亮层+行号，opts.readonly）、`caretLineOf`（213）/`caretColOf`（226）、
  `indentLines`（323，4 空格）/`indentOnEnter`（299，拷贝前导空白）、
  `editorLineRange`（59，委托 fx/code.js `maincLineOffsetRange` 单源）、
  `EDITOR_TABS_MAX = 10`（16）。`static/js/ui/codeeditor.js`（153513 字节）——
  `openEditorFile`（1526）、tab 条渲染 `renderTabs`（748）、脏点判定
  `isTabDirty`（1668）、关闭确认 `showConflictModal`/`closeTab`（1957/1594）、
  光标行高亮 `setActiveLine`（1730）+ gutter active、跳行
  `editJumpToLine`（1755）/`editJumpToFile`（1825）、只读 tab（非 UTF-8 走
  `renderReadonlyNote` 1471）、Ctrl+S `saveActiveTab`（1854）。
  接线 `static/index.html:4430 import { initCodeEditor }` + `:4842 initCodeEditor()`，
  标签条容器 `:2988 <div class="code-tabs" id="code-tabs">`，样式 `:1700 .code-tabs`。
  测试：`tests/js/codeeditor.test.mjs`（41 用例：`:35` tab 条脏点/只读/关闭钮、
  `:82/91/98/104` 三明治与 readonly、`:125/136` caretLineOf/caretColOf、
  `:148-191` indentOnEnter 五形态、`:213-227` indentLines、`:203` 跳行越界、
  `:277` EDITOR_TABS_MAX）——实测 `node --test tests/js/codeeditor.test.mjs` 全绿。
  CDP 冒烟 `.scratch/code-viewer-editor/smoke-02.mjs`：标签条空态 111、三明治 119、
  编辑脏点 143、高亮层随输入 145、Tab/Enter 缩进 165/179、光标行高亮 195、
  两 tab 与切换保内容 205/216、关闭非脏/脏 tab 确认与取消 229/232/235、
  GBK 只读 tab 267、大纲点击选中目标行 282。
  验收逐条对照：① fx 纯函数全在 ✓ ② ui 胶水全在 ✓ ③ ui/codeview 树点击接
  openEditorFile（`ui/codeview.js:388` 起）✓ ④ index.html/CSS + 单测 ✓
  ⑤ node --test 绿 + smoke-02 项覆盖 ✓。附：工单说「本票保存不接」，实际保存链路
  已在同 feature 工单 03 接通（`/api/code/save`），属演进不冲突。

(End of file - total 23 lines)
</content>