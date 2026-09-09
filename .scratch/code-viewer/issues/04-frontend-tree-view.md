# 04 — 前端：代码 tab 骨架 + 文件树 + 只读代码视图

**要做什么：** 学生打开「代码」标签页 → 点「选择文件夹」（服务端原生对话框）→ 左侧出现可收起文件树（目录在前、码点序、噪音目录不出现）→ 点树内文本文件，中间出现带行号 + 语法高亮的只读视图。端到端可手动验证，无 minimap。

**被谁阻塞：** 01。

**状态：** resolved

- [x] index.html：导航 `<button data-tab="code">`（「代码」+ title 一句话）+ tab-code 区（顶栏：选择文件夹按钮 / 当前目录路径；三栏容器：左树 / 中视图 / 右侧栏占位）+ 宿主 module script import ui/codeview.js 并 initCodeViewer()。
- [x] fx/codeview.js：`buildCodeTree(files)`（扁平清单 → 嵌套节点，目录在前同级码点序）/ `codeTreeHTML(nodes)`（原生 details/summary，不 import fx/master.js——同构新写避免母版语义耦合）/ `codeLineNumbersHTML(count)` / `codeViewHTML(content, lang)`（gutter 行号 + pre white-space:pre 不换行、同一 font/line-height 保证行对齐；高亮走 fx/highlight.js highlightText 单源）；末尾 Object.assign(window, …) 兼容。
- [x] ui/codeview.js：`initCodeViewer()`（选择文件夹 → apiPost /api/pick-directory（取消静默）→ `openCodeViewer(path)`；树点击委托：文件 → apiGet /api/code/file → 渲染 + memo（key = dir+path）；目录 → 原生展开收起；加载三态 + 中文错误 toast）+ 导出 `openCodeViewer(dir)`（先存 dir 再切到 tab-code 并加载）。
- [x] tests/js/codeview.test.mjs（buildCodeTree 排序与嵌套 / codeLineNumbersHTML / codeViewHTML 行数一致与高亮分发与转义）；既有 tests/js 全绿、pytest 全绿。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点）：`src/contest_generator/static/index.html`
  ——导航按钮 `:2947 <button data-tab="code" …>`、`#tab-code` 区 `:2972`（含三栏
  `.code-layout` `:1646` 与树宽变量 `--code-tree-w`）、宿主接线
  `:4439 initCodeViewer()` 与 `:4386` 静态 import fx/codeview.js。
  `static/js/fx/codeview.js`：`buildCodeTree`（25 行，目录在前码点序，`sortCodeTree` 55）、
  `codeTreeHTML`（137，原生 details/summary）、`codeLineNumbersHTML`（206）、
  `codeViewHTML`（264，gutter + pre `white-space:pre`）、高亮走
  `static/js/fx/highlight.js:122 highlightText`（单源，`languageOf` 19）。
  `static/js/ui/codeview.js`：`initCodeViewer`（855）、`openCodeViewer`（388，
  先存 dir 再切 tab-code）、`loadCodeDir`（394）、树点击 memo（`fetchCodeFile` 123）。
  测试：`tests/js/codeview.test.mjs:29/43`（buildCodeTree 排序嵌套与顺序无关）、
  `:55`（codeTreeHTML details/转义）、`:93`（行号）、`:103/112`（codeViewHTML 行数
  一致与转义）——实测 `node --test tests/js/codeview.test.mjs` 31 passed / 0 fail。
  验收逐条对照：① index.html 导航 + tab-code + 宿主接线 ✓ ② fx 四个纯函数 + 高亮单源 ✓
  ③ ui initCodeViewer/openCodeViewer + 懒加载 memo + 三态 ✓ ④ js 单测与 pytest 绿 ✓。
