# 07 — 代码区视觉细节打磨

**要做什么：** 代码区视觉向 VSCode 靠拢（深/浅双主题）：字体栈与字号/行高微调（走 `--code-font-size` 链，Ctrl+滚轮缩放继续联动）；缩进引导线（indent guides，按行内前导空白逐行绘制在空白区，不覆盖文字，双主题自动适配）；括号配对从下划线升级为 VSCode 式描边框；当前行/选区/滚动条观感微调。

**被谁阻塞：** 无——可立即开始。

**Type:** task
**Status:** resolved

## 实现要点

- 缩进引导线挂标记层同族的纯背景层（`pre.code-marks` 或新增同构层），逐行按前导空白绘制竖线；窗口化（08）后该层同样只画窗口行。
- 括号配对：描边框样式替换/升级现有下划线（保留降级路径）。
- 双主题各截一张 CDP 图对比验收；不改变字体度量导致三明治错位（font/line-height/padding/tab-size 仍逐行 1:1）。

## 验收 checklist

- [x] 深色 + 浅色各一张截图：缩进引导线可见、对齐、不覆盖文字。
  **2026-09-09 第七轮 CDP 实跑**：`smoke-07.mjs` 写出 `shot-07-visual-dark.png`（78903B）/ `shot-07-visual-light.png`（80376B）
  并入库；同脚本断言「缩进引导线渲染（≥3 条）」「浅色主题引导线仍渲染（≥3）」。
- [x] 括号配对描边（光标旁配对括号）样式正确，双主题可辨。
  断言：光标落 `{` 后 `.code-mark-bracket` == 2（`index.html:1890` 的 `box-shadow: inset 0 0 0 1.5px`）。
- [x] Ctrl+滚轮缩放后引导线与文字仍对齐。
  断言：`--code-zoom: 1.5` 后 gutter 行高 == 高亮行高（实测 31.1875 == 31.1875）+ 引导线仍渲染。
- [x] 既有折叠/查找/选中词/行号/滚动不回归；`node --test` 全绿。
  **第七轮实测**：`smoke-01.mjs` 24/24、`smoke-03.mjs` 9/9、`smoke-07.mjs` 7/7、`smoke-08.mjs` 13/13、
  `smoke-10-guides-scroll.mjs` 5/5；`node --test tests/js/*.test.mjs` **1393 pass / 0 fail**。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。

## Comments

- 2026-09-09 第七轮：验收项全部由 CDP 实跑关闭（B2 截图 + 三条断言 + 回归面），
  `Status: ready-for-agent → resolved`；`.scratch/real-acceptance/issues/01` 的 **B2 同时勾选**。
