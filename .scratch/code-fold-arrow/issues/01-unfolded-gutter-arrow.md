# 01 — 未折叠态 gutter 缺折叠箭头（可折叠行没有 ▾，鼠标折叠入口不存在）

**要做什么：** `code-editor-vscode-polish/07` 验收项②原文「行号列左侧（或行号列与代码之间）折叠箭头：
**可折叠行显示 ▸（折叠）/ ▾（展开）；点击切换**」目前只兑现了「折叠后 ▸ 可点击展开」这一半：
未折叠态 gutter 走平铺行号渲染（无箭头），可折叠行没有任何鼠标折叠入口——只有知道
Ctrl+Shift+[ 的用户能折叠，鼠标用户无从发现该能力。

**被谁阻塞：** 无——可立即开始。

**Type:** task
**Status:** ready-for-agent

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

## 验收 checklist

- [ ] 未折叠态：可折叠行 gutter 显示 ▾，点击即折叠（占位行出现 + 行号跳号）。
- [ ] 折叠态 ▸ / 占位行 / Ctrl+Shift+[/] 四条既有路径不回归（`smoke-01.mjs` / `smoke-07.mjs` 已覆盖）。
- [ ] tests/js：纯件单测（单折叠区 / 多折叠区 / 嵌套 / 无折叠区空数组 / 行号与 fold 索引对应）。
- [ ] CDP 冒烟 `smoke-01.mjs`：未折叠箭头在场 + 点击折叠断言。
- [ ] `smoke-09.mjs` 5000 行回车/Tab 同步耗时仍 < 50ms 均值（性能不退化）。

## Comments

- 2026-09-09 第六轮盘点发现（B1 补折叠断言时顺手实测）：登记为独立工单，不在盘点会话内实现
  （盘点口径 = 只做盘点表真待办项；此为验收复核中新发现的产品缺口）。
