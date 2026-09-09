# 04 — 文件内查找高亮 + 计数

**要做什么：** 侧栏「查找」输入非空时，编辑器内所有命中片段加标记层高亮（当前命中更醒目），输入框旁显示「第 N / 共 M 处」，Enter / Shift+Enter 循环跳转，替换输入行显示「将替换 N 处」。

**被谁阻塞：** 无——可立即开始（本工单同时交付「标记层基础设施」，供 05 / 06 复用）

**状态：** resolved

- [ ] 标记层基础设施：.code-edit 三明治内「高亮层之上、textarea 之下」插入仅背景标记层（同字体度量、文本透明、pointer-events:none、随滚动天然跟随）；标记 span 内容先 esc 再包
- [ ] 查找输入非空 → 编辑器内所有命中行内片段高亮（淡 accent 底）；当前命中（第 N 个）样式更醒目（accent 底 + 左侧竖线或描边）
- [ ] 计数显示「第 N / 共 M 处」；无命中显示「无匹配」；输入变化即时重算（含编辑内容后重算）
- [ ] Enter / Shift+Enter 循环上/下一个命中并滚动居中 + 保持当前命中样式联动；命中列表点击项与当前命中联动（复用既有跳转）
- [ ] 查找命中区域与行内查找列表一致（大小写不敏感、子串语义、空针无高亮）
- [ ] 按 Esc / 清空输入 → 编辑器高亮清除
- [ ] 替换输入行显示「将替换 N 处」（与「全部替换」按钮并存，不改变其行为）
- [ ] 标记层不破坏既有选区 / 光标 / 当前行高亮；深浅主题可辨
- [ ] tests/js：命中区段计算（多行 / 重叠 / 空针 / 转义）、标记层 HTML（esc、当前命中类）单测
- [ ] CDP 冒烟：输入查找词 → 高亮元素数 = 命中数、计数文案正确；Enter 切到下一命中

**补充：** 标记层是共享基础设施：同类「背景标记」渲染逻辑抽出（fx 纯件），05 选中词与 06 括号配对通过同一渲染入口挂自己的标记清单（不同类名）。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点；**此前「grep 未见实现」的怀疑不成立**）：
  标记层基础设施 = `src/contest_generator/static/js/fx/code-marks.js`
  （`codeFindRanges` 77、`codeMarksHTML` 124，仅背景 span、文本透明、
  pointer-events:none）+ `fx/codeeditor.js:201-204` 三明治内
  `<pre class="code-marks">` 层（高亮层之上、textarea 之下，样式
  `static/index.html:1877 .code-marks`）。
  UI `src/contest_generator/static/js/ui/codeview.js`——`applyEditorFind`
  （583，单入口：标记层 + 计数 + 替换计数）、`updateFindCount`（567：
  「第 N / 共 M 处」/「无匹配」/ 空查询隐藏）、`renderFindPanel`（544，命中行
  列表可点击）、Enter/Shift+Enter（1022-1034 调 `editorFindStep(±1)`）、
  Esc 清空（1038-1041）、替换后重算（1075）。DOM：
  `static/index.html:3025 #code-find-input`、`:3026 #code-find-count`、
  `:3030 #code-replace-count`（「将替换 N 处」，codeview.js:586-594）。
  测试：`tests/js/code-marks.test.mjs` 13 用例（`:12` 大小写不敏感/多行/1 基行号、
  `:21` 空针与不重叠、`:32` trim 一致、`:44` HTML 转义、`:55` 当前命中优先类、
  `:70` 选中词/括号类分层、`:79` error kind 优先级）——实测
  `node --test tests/js/code-marks.test.mjs` 全绿（含在 78 passed 批次）。
  CDP 冒烟 `.scratch/code-editor-vscode-polish/smoke-04.mjs` 11 项：
  标记层 3 处 + 计数「第 1 / 共 3 处」（103）、Enter → 第 2 处 + 选区覆盖（118）、
  Shift+Enter 回第 1 处（134）、Esc 清空（143/205）、「将替换 3 处」（159）、
  「无匹配」+ 替换计数隐藏（170）、编辑后重算（193）。
  验收逐条对照：① 标记层基础设施 ✓ ② 命中高亮 + 当前命中更醒目 ✓
  ③ 计数文案 + 即时重算 ✓ ④ Enter/Shift+Enter 循环 + 列表联动 ✓
  ⑤ 与 fileFindFilter 同语义（大小写不敏感子串、空针无高亮）✓ ⑥ Esc/清空清除 ✓
  ⑦ 「将替换 N 处」✓ ⑧ 标记层不挡选区/光标（pointer-events:none + 透明文字）✓
  ⑨ 单测 ✓ ⑩ CDP 冒烟 ✓。
