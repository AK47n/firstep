# 02 — Ctrl+/ 注释切换

**要做什么：** Ctrl+/ 在代码编辑器中切换注释：.c/.h 对选区（无选区=当前行）逐行切换 `//` 行注释；多行选区中若每行已有 `//` 则去掉、否则添加；当选区内容自身含 `/* ... */` 块注释时切换为块注释（加/去 `/* */` 包围，行为对齐 VSCode）。XML：逐行切换 `<!-- -->`。注释切换后选区/光标保持合理位置。

**被谁阻塞：** 01（复用其 keydown 管线与 lineRangeOf 基础）。

**Type:** task
## Answer

已实现并验证：

- 新 fx 纯件 `src/contest_generator/static/js/fx/code-comment.js`：`toggleLineComment`
  （.c/.h `//` 逐行；XML `<!-- -->` 成对逐行）与 `toggleBlockComment`
  （`/* */` 加/去包围：精确块→去、混合选区含块→去最外层对、无块→加）。
  逐行规则：触及行 = 选区行（终点落行首含行尾换行时扩展，与 lineRangeOf 同
  规则）；空白行跳过；全部非空行已注释→去，否则→加（插前导空白之后）。
- 单测 `tests/js/code-comment.test.mjs` 12 例全绿（单行/多行/空行/缩进/已注释
  去除/XML 加去/块加/块去/混合选区）。
- keydown 管线注册 Ctrl+/（仅 c/xml 编辑态、IME 守卫、只读早退）；帮助弹窗
  数据单源同步。
- CDP 冒烟 `.scratch/code-page-vscode-overhaul/smoke-02.mjs` 7/7 PASS。
- 全量测试 1183 例通过；code-review 双轴无硬违规（语义取舍：无块标记选区
  走逐行注释对齐 VSCode，块注释「加」为纯件可达能力，已记录）。

**Status:** resolved

## 实现要点

- fx 纯件：`toggleLineComment(text, selStart, selEnd, {lineComment})`、`toggleBlockComment(text, selStart, selEnd, {blockOpen, blockClose})`；按语言分派（c/h 行注释 `//`、xml 行注释 `<!--`/`-->`）。
- 空行也参与逐行注释切换（VSCode 行为：空行不加注释前缀，或按既有约定，实现时以单测固定）。
- 只读文件 / .md 预览态不响应。

## 验收 checklist

- [x] 纯件单测覆盖：单行加/去注释、多行逐行、空行、块注释加/去、xml 注释。
- [x] 深色主题下 .c 文件 Ctrl+/ 逐行切换；含 `/* */` 选区切换块注释。
- [x] XML 文件 Ctrl+/ 逐行 `<!-- -->` 切换。
- [x] 撤销行为不在此工单（归 04），但切换后选区位置合理。
- [x] 既有测试全绿。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
