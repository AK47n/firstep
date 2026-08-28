# 效果 diff 渲染美化（diff-restyle）

## 问题陈述

深化 / 任务执行后的 main.c 前后 diff（`reviseRenderDeepenDiff`，ui/generate-revise.js:435-461）观感粗糙：
- 全部内联样式 + 固定浅色（`#f7f7f7` / `#2e7d32` / `#c62828` / `#777`），深色主题下刺眼、明暗不统一；
- 行着色是内联 span 的整行色块，无左右 padding、无 +/− 对齐列、行与行之间边界不清；
- 代码块无边框圆角，与卡片其它组件风格不一致。

用户反馈（截图）：红绿条纹式显示"不是很美观"。

## 目标

把效果 diff 渲染成主题化的 GitHub 风格行级视图：
- 明暗双主题自动适配（复用既有 CSS 变量，不新造颜色值）；
- 每行 = 「+/− 符号列 + 内容」对齐；新增行绿底、删除行红底、上下文行灰；
- 代码块等宽字体、圆角边框、横向滚动、行内 padding；
- hunk 可折叠、统计行保留；
- 纯函数进 fx 模块（可单测 + fx-guard 护栏），渲染调用点形状不变（`mainDiffHTML(diff, entity)`）。

## 用户故事

1. 深色 / 浅色主题下，diff 块均清晰可读、颜色和谐。
2. 每行有固定宽度的 +/− 符号列，内容对齐。
3. diff 块有边框、圆角、行内 padding，与卡片风格一致。
4. hunk 仍按「标题 + 可折叠代码块」展示，行为不变（默认折叠）。
5. 统计行（新增 +N 行 · 删除 −N 行 · N 处改动）保留，颜色用主题变量。
6. 深化面板与任务结果面板两处复用同一渲染器，文案参数（entity）保留。
7. 无差异 / main_diff 为 null 时的占位文案不变。

## 实现决策

- 新模块 `src/contest_generator/static/js/fx/diff.js`（纯函数，只 import core.js 的 `esc`）：
  - `mainDiffHTML(diff, entity)` → 整块 HTML（统计行 + hunks），签名与旧 `reviseRenderDeepenDiff` 对齐；
  - `diffStatsLineHTML(stats, name)` → 统计行；
  - `diffLineHTML(entry)` 私有 → 单行（gutter + text）；
  - window 桥挂载（兼容探针）。
- ui/generate-revise.js：删除 `reviseRenderDeepenDiff` / `reviseDiffLineHtml`，改为 `import { mainDiffHTML } from "../fx/diff.js"`；调用点 `reviseRenderDeepenDiff(data.main_diff)` → `mainDiffHTML(data.main_diff)`；导出面移除 `reviseRenderDeepenDiff`。
- ui/generate-tasks.js:26 import 改 `reviseGetDir` from generate-revise + `mainDiffHTML` from fx/diff.js；调用点 316 同步改。
- index.html：新增 `.diff-stats` / `.diff-hunk` / `.diff-body` / `.diff-line` / `.diff-gutter` / `.diff-text` 类（放在任务卡样式区附近），全部用既有变量：`--panel-2` / `--border` / `--ok` / `--ok-bright` / `--ok-dim` / `--danger` / `--danger-dim` / `--muted` / `--mono`。
- 行结构：`<div class="diff-line diff-add|diff-del|diff-ctx"><span class="diff-gutter">+|−| </span><span class="diff-text">…</span></div>`；行背景 = `var(--ok-dim)` / `var(--danger-dim)`（整行），文字 = `var(--ok-bright)` / `var(--danger)` / `var(--muted)`。
- 测试：
  - 新 `tests/js/diff.test.mjs`：统计行文案与颜色类、add/del/ctx 行结构与转义、hunk 标题回退（「第 N 行附近」）、main_diff null/undefined / 空 hunks 占位、entity 文案注入（深化 / 任务）、window 桥导出存在性；
  - fx-guard.test.mjs `DOMAINS` 登记 `diff.js`；
  - JS 全量绿；pytest 不动（后端零改动）。

## 范围外

- 行号（后端 main_diff 无行号字段，不造伪行号）；
- diff 内容高亮词法（仅整行着色）；
- 折叠状态持久化；
- 修改后端 main_diff 结构。
