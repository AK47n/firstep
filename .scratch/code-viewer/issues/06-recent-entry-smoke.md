# 06 — 最近记录卡「查看代码」入口 + CDP 全链路冒烟

**要做什么：** 学生打开工具，最近生成记录卡上一键进代码查看器；全链路自动冒烟证明 01–05 都能跑通。端到端：记录卡加「查看代码」小按钮（不触发整卡复制路径行为）→ 点击切到「代码」tab 并加载该 output_dir；CDP 冒烟脚本走完「打开 tab → 样本目录 → 树加载 → 大纲跳行 → 搜索跳转 → 最近卡按钮」全链路。

**被谁阻塞：** 04、05（入口依赖 openCodeViewer 桥；冒烟覆盖 05 的面板链路）。

**状态：** resolved

- [x] fx/recent.js recentChipHTML 加「查看代码」按钮（class .code-open-btn、data-dir、stopPropagation）；ui/recent.js 点委托加分支 → 调 openCodeViewer(dir)（经宿主层桥接，避免 ui 模块互相 import——实现期以现有模块约定为准）。
- [x] .scratch/code-viewer/smoke.mjs：CDP 冒烟（临时样本工程目录；树展开/点文件加载/大纲跳行/搜索命中跳转/最近卡按钮；不真生成、零写库）；冒烟清单保持全绿。
- [x] 全量回归：pytest 全量 + tests/js 全量绿。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点）：
  `static/js/fx/recent.js:50` 记录卡内 `<button class="recent-code-open"
  data-code-dir="…">查看代码</button>`（工单原文写的 `.code-open-btn` / `data-dir`
  与实际类名 `recent-code-open` / `data-code-dir` 不同，**行为等价**：同为小按钮 +
  携带 output_dir）；`static/js/ui/recent.js:15` 直接 import
  `openCodeViewer`（避免 ui 互相 import，与工单「以现有模块约定为准」一致）、
  `:60-61` `e.stopPropagation()` 后 `openCodeViewer(codeBtn.dataset.codeDir)`——
  不触发整卡复制路径。
  CDP 冒烟 `.scratch/code-viewer/smoke.mjs`（20065 字节）覆盖：打开样本目录
  （111-112 经 `openCodeViewer`）、树/文件加载、大纲跳行（234）、跨文件搜索跳转
  （250/256）、Ctrl+F（268）、最近卡按钮（363-370 断言 `recent-code-open` +
  `data-code-dir` + 删除钮共存）。
  验收逐条对照：① 记录卡按钮 + 委托分支 + stopPropagation ✓（类名不同、行为一致）
  ② smoke.mjs 落盘且清单覆盖 01–05 全链路 ✓ ③ 回归：本次盘点实测
  `node --test tests/js/codeview.test.mjs` 31/31 绿，pytest 基线见盘点表 ✓。
