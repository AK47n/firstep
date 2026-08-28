# 工单 01：效果 diff 前端美化（fx/diff.js + CSS + 测试）

Status: resolved

## 目标

实现 spec（.scratch/diff-restyle/spec.md）的前端部分：
新 fx/diff.js（mainDiffHTML / diffStatsLineHTML + window 桥）→ 替换 ui/generate-revise.js 的 reviseRenderDeepenDiff / reviseDiffLineHtml（删除）→ ui/generate-tasks.js 改 import 与调用点 → index.html 新增 .diff-* 主题化样式 → tests/js/diff.test.mjs + fx-guard 登记。

## 验收

1. 深色 / 浅色主题下 diff 块均用 CSS 变量渲染（grep index.html 不得出现新硬编码颜色 #f7f7f7 / #2e7d32 / #c62828 / #e8f5e9 / #fdecea）。
2. fx/diff.js 只 import core.js 的 esc；纯函数无 DOM。
3. 行结构含 `.diff-gutter` 与 `.diff-text`；add/del/ctx 三种类。
4. ui/generate-revise.js 无 reviseRenderDeepenDiff / reviseDiffLineHtml 残留（grep）。
5. index.html / ui/generate-tasks.js 无 reviseRenderDeepenDiff 引用（grep）。
6. 既有行为保留：占位文案、hunk 标题回退、entity 参数、默认折叠。
7. tests/js/diff.test.mjs 覆盖：统计行、三行类型、转义、标题回退、null/空占位、entity 文案、桥导出；fx-guard DOMAINS.diff.js 登记 3 导出（mainDiffHTML / diffStatsLineHTML / window 桥挂载的全局名）。
8. JS 全量绿（node --test tests/js/*.test.mjs）。

## 实现要点（已定）

- `mainDiffHTML(diff, entity)` 返回：null/undefined/空 hunks → 原占位文案（muted 行）；否则统计行 + `<details class="diff-hunk">` 列表。
- `diffStatsLineHTML(stats, name)`：`<div class="diff-stats reason">…新增 <span class="diff-count add">+N</span> 行 · 删除 <span class="diff-count del">−N</span> 行 · N 处改动…`。
- 行：`<div class="diff-line {kind}"><span class="diff-gutter">{+|-| }</span><span class="diff-text">esc(text)</span></div>`；gutter 用 `−`（U+2212）与统计行一致。
- CSS 用既有变量；`.diff-body` 容器 `overflow:auto; white-space` 由 `.diff-text` 承担（pre 语义 = `white-space:pre`）；`.diff-line` `min-width:max-content` 保证横向滚动时行背景整行延伸。

## 测试命令

node --test tests/js/*.test.mjs
