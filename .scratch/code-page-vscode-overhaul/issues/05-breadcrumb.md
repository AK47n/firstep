# 05 — 文件路径面包屑

**要做什么：** 标签条下方显示当前文件相对工程根的路径分段（如 src / main.c），分段可点击；点击目录段 → 文件树展开到该目录并滚动高亮该节点；未打开文件 / 空态不占位；路径过长时截断（中间省略）。

**被谁阻塞：** 无——可立即开始。

**Type:** task
## Answer

已实现并验证：

- fx/codeview.js：`breadcrumbSegments(relPath)`（逐段累积
  {name, path, isDir}）与 `breadcrumbHTML(segments)`（目录段按钮
  data-breadcrumb-dir、文件段按钮 data-breadcrumb-file、分隔符 ›、超长名
  截断 … + title 全量路径、全部转义）；codeTreeHTML 目录 `<details>` 补
  data-dir-path。
- ui/codeview.js：renderBreadcrumb()（随 onActiveTabChanged 刷新，无活动
  标签隐藏不占位）；revealTreePath(dirPath)（逐级 details.open +
  scrollIntoView + .code-tree-reveal 高亮动画 1.2s 自动清除，CSS.escape
  防注入）；面包屑点击 delegation。
- index.html：`.code-breadcrumb` 行（标签条下）+ CSS（变量驱动双主题）。
- 单测 tests/js/codeview.test.mjs 22 例全绿（+4 面包屑/树 data 属性）；
  CDP 冒烟 smoke-05.mjs 11/11 PASS（含标签切换同步、目录定位、文件段
  打开、深层路径）；深色截图 shot-05-breadcrumb-dark.png。

**Status:** resolved

## 实现要点

- fx 纯件：相对路径 → `[{name, path}]` 分段 + 渲染字符串（HTML 转义、长度截断规则），可单测。
- 文件树渲染（`fx/codeview.js` codeTreeHTML）给目录 `<details>` 补 `data-dir-path` 属性（保持既有测试全绿）。
- 新增 `revealTreePath(dirPath)`：逐级设置 `<details>.open`，滚动到目标节点并加高亮 class（短暂消除）。
- 面包屑与标签激活联动：切标签 / 打开文件时更新；目录段点击调用 revealTreePath；文件段点击等价于打开该文件。

## 验收 checklist

- [x] 纯件测试：路径分段、空路径、根路径、截断渲染；HTML 转义（含 `<`、`&`）。
- [x] 深色主题下打开多层目录文件，面包屑显示正确；点击目录段文件树展开并高亮。
- [x] 文件树既有展开/折叠/点击打开行为不回归。
- [x] 未打开文件时面包屑区域不占位（或显示合理空态）。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
