# 01 — 未折叠态 gutter 缺折叠箭头（可折叠行没有 ▾，鼠标折叠入口不存在）

**要做什么：** `code-editor-vscode-polish/07` 验收项②原文「行号列左侧（或行号列与代码之间）折叠箭头：
**可折叠行显示 ▸（折叠）/ ▾（展开）；点击切换**」目前只兑现了「折叠后 ▸ 可点击展开」这一半：
未折叠态 gutter 走平铺行号渲染（无箭头），可折叠行没有任何鼠标折叠入口——只有知道
Ctrl+Shift+[ 的用户能折叠，鼠标用户无从发现该能力。

**被谁阻塞：** 无——可立即开始。

**Type:** task
**Status:** resolved

## 证据（2026-09-09 在途盘点第六轮 CDP 实测）

- 未折叠：`document.querySelectorAll('#code-viewer [data-fold]').length === 0`、gutter 文本 `1|2|3`
  （`.scratch/code-page-vscode-overhaul/probe-fold.mjs` 步骤 A）。
- 折叠后：`[data-fold]` = 1、gutter `▸1|2`、点箭头可展开（同脚本步骤 B/C——折叠态路径正常）。
- 渲染单源：`ui/codeeditor.js` `winBuild`（`gutter = viewModel ? codeFoldGutterLines(viewModel.lines) : lines.map(codeGutterLineHTML)`）
  ——只有折叠态（viewModel 非空）才走折叠 gutter；纯件 `fx/code-fold.js` 的箭头分支本就支持
  `folded: false`（▾），但没有「未折叠 → 构造 foldStart 行」的调用方。
- 既有冒烟同样只测折叠态箭头：`.scratch/code-editor-vscode-polish/smoke-07.mjs:89` 只断言「打开 → 8 行 gutter」，
  `:113` 点的是折叠后的 `.code-fold-arrow`。

## 实现要点

- 纯件新增「未折叠 gutter 行描述」：按 folds 给每个折叠区开行打 `{no, foldStart: true, fold: idx, folded: false}`，
  仍由 `codeFoldGutterLines` 渲染（箭头 markup 单源，不复制）。
- `winBuild` 未折叠分支：`folds.length ? codeFoldGutterLines(codeFoldModelGutterLines(lines, folds)) : 平铺行号`
  （无折叠区零变化）。
- 性能：`winBuild` 只在结构变更（行数变化）时走，逐键非结构编辑走 `winPatchEdit`；需复测 5000 行回车/Tab 耗时（smoke-09 阈值 <50ms 均值）。
- 注意与 `winCache.foldedView` 增量 patch 前提（第六轮修复）的接缝：gutter 来源变化必须走 winBuild。

## 实现记录（第七轮，2026-09-09 同会话 · CDP 真机实跑）

| 层 | 落地 | 位置 |
|---|---|---|
| 纯件 | 新增 `codeFoldModelGutterLines(lines, folds)`：平铺行描述 + 折叠区开行 `{foldStart: true, fold: idx, folded: false}`；乱序 folds 也按数组下标（= `foldedSet` 键）；`null`/空数组安全 | `fx/code-fold.js`（导出 + `window` 挂载） |
| 接线 | `winBuild` 未折叠分支：`folds.length ? codeFoldGutterLines(codeFoldModelGutterLines(lines, folds)) : 平铺行号`（无折叠区零变化） | `ui/codeeditor.js:838-846` |
| 顺序修正 | **`folds` 计算提到 `winBuild` 之前**——原来 `renderPane` 先 `winBuild` 后算 folds，改完若不调序则「打开文件首屏无箭头、编辑一次才出现」 | `ui/codeeditor.js` `renderPane` |
| 单测 | +5 例（单区 / 多区乱序 / 嵌套 / 空输入 / 与 `codeFoldGutterLines` 联合渲染 ▾ 断言） | `tests/js/code-fold.test.mjs`（18 pass） |
| CDP | `smoke-01.mjs` 补 5 项：未折叠 ▾ 在场 → 点箭头折叠（占位 + ▸ + 行号跳号）→ 再点回未折叠 ▾；并把「展开态 gutter」断言更新为 `▾1|2|3` | 实跑 **24/24 PASS** |
| 回归 | `smoke-07.mjs` 折叠四条路径 **9/9**、`smoke-01` 折叠/保存 8 项全绿；`tests/js` 全量 **1393 pass / 0 fail** | — |

## 验收 checklist

- [x] 未折叠态：可折叠行 gutter 显示 ▾，点击即折叠（占位行出现 + 行号跳号）。
- [x] 折叠态 ▸ / 占位行 / Ctrl+Shift+[/] 四条既有路径不回归（`smoke-01.mjs` / `smoke-07.mjs` 已覆盖）。
- [x] tests/js：纯件单测（单折叠区 / 多折叠区 / 嵌套 / 无折叠区空数组 / 行号与 fold 索引对应）。
- [x] CDP 冒烟 `smoke-01.mjs`：未折叠箭头在场 + 点击折叠断言。
- [ ] `smoke-09.mjs` 5000 行回车/Tab 同步耗时仍 < 50ms 均值（性能不退化）。
  **本轮实测未达标**：回车均值 ~116ms、Tab ~52ms（阈值 50ms）。**与本工单无关**——未折叠箭头只在
  结构变更时重建 gutter 字符串（`winBuild` 本来就要走），本轮定位到的真凶是
  `winApplySize` 的宽度缓存被行数变化重置 → 每次回车重新探针测量 → 强制整树深布局 ≈50ms
  （已修：见下「本轮同会话修复」第 1 项，修后探针不再触发）。剩余 ~50ms 为
  `taWindowApply`/`winRender` 内**写样式后读几何**的强制布局（时间线实测：`winApplySize` 后到
  `taWindowApply` 结束占 48.5ms），属窗口化渲染的布局成本，需单独工单优化（不在本工单范围）。

## Comments

- 2026-09-09 第六轮盘点发现（B1 补折叠断言时顺手实测）：登记为独立工单，不在盘点会话内实现
  （盘点口径 = 只做盘点表真待办项；此为验收复核中新发现的产品缺口）。
- 2026-09-09 第七轮实现（本会话）：纯件 + 接线 + 5 单测 + CDP 5 项断言，实跑 24/24；
  `folds` 计算顺序修正（否则首屏无箭头）。性能项见上，与本报缺口无因果。
