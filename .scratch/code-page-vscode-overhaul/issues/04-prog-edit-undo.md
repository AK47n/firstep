# 04 — 程序化编辑不打断撤销栈

**要做什么：** Tab 缩进 / Enter 自动缩进 / 括号自动闭合 / 行操作（01）/ 注释切换（02）/ 查找替换（03）等程序化编辑之后，Ctrl+Z 连续撤销、Ctrl+Y 连续重做，与键盘直接输入一致；焦点在编辑器内时快捷键优先编辑器。

**被谁阻塞：** 01（行操作）、03（替换）——需覆盖的编辑路径先就位。

**Type:** task
## Answer

已实现并验证：

- `applyEdit` 重构：优先 `execCommand("insertText")`（公共前后缀 diff → 最小
  替换区间 → 浏览器原生撤销栈一步一撤；Chrome 下 input 事件同步模型/高亮，
  选区最终落位 + 当前行/状态轻量刷新，避免重复全量渲染）。execCommand 不可用
  /失败 → 降级直赋值（现状行为）+ 快照式自定义撤销栈（undoStack/redoStack，
  上限 200 条；nativeUndo 关闭时 Ctrl+Z/Y/Shift+Z 拦截走快照）。
- 覆盖全部程序化编辑路径：Tab / Shift+Tab / Enter / 括号闭合与 Backspace /
  行操作（01）/ 注释切换（02）/ 替换单个与全部（03）；手输与原生 Ctrl+Z/Y
  不受影响（焦点在编辑器内即浏览器默认撤销）。
- CDP 冒烟 `.scratch/code-page-vscode-overhaul/smoke-04.mjs` 18/18 PASS：
  每条路径 撤销→重做→值一致，含手输回归；全量测试通过。

**Status:** resolved

## 实现要点

- 程序化编辑优先走浏览器保留原生撤销栈的写入路径（`execCommand("insertText")` / `insertLineBreak` 等，实测为准）；失败降级为现有直赋值，再降级为快照式自定义撤销栈（仅覆盖程序化编辑段，与原生栈拼接）。
- 关键属性：写完文本与选区后 `selectionStart/End` 正确恢复，undo/redo 后选区合理。
- 冒烟验证各路径：Tab、Shift+Tab（01）、Enter、括号闭合与 Backspace、行操作（01）、注释切换（02）、替换（03）后 Ctrl+Z/Y。

## 验收 checklist

- [x] 深色主题下逐路径验证：Tab / Shift+Tab / Enter / 括号 / 删行 / 移动行 / 注释 / 替换 后 Ctrl+Z 撤销、Ctrl+Y 重做，文本与选区正确。
- [x] 连续多次程序化编辑后可连续 Ctrl+Z 逐步回退（不清空历史）。
- [x] 键盘直接输入（字符、Backspace）的撤销行为不回归。
- [x] 纯件/胶水可测部分补测；冒烟覆盖编辑器内焦点切换。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
