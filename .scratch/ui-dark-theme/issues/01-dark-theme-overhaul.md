# 01 — 全工具深色科技感换皮（单文件 UI 主题重构）

**What to build:** 把 `src/contest_generator/static/index.html` 的 UI 从"浅色 Tailwind 蓝 + 大量硬编码浅色"整体换皮为**深色科技感单主题**：近黑底 `#0d1117` + 青色强调 + 克制平面质感；自绘原生控件（select/checkbox/文件上传/滚动条）；代码块等宽字体换 JetBrains Mono（本地自托管）；覆盖全部 7 个 tab + 2 处 SSE 进度面板 + ref-files 弹层。**不动任何布局结构与 JS 行为逻辑**，后端零改动。

**Status:** resolved（2026-08-12，用户浏览器人工验收通过）

## 验收记录（2026-08-12）

- 用户浏览器人工验收：**8 步生成流程走通，生成工程编译无错**（无白底/浅色残留、可读性问题反馈）；7 tab / ref-files 弹层 / SSE 进度面板随 8 步流程一并过眼，未报问题。
- 自检（实施侧）：`grep "https\?://"` 只剩两处 placeholder 文本；`git diff` 变更行全部落在 `<style>` 块内（布局/JS/class/id 零改动）；pytest **1111 全绿** + `mypy src` 干净（33 文件）+ `node tests/js/sse-parser.test.mjs` 过；`git status` 只出现 `static/index.html` + 本工单文件。

## 实施记录（2026-08-12）

- **令牌层**：`:root` 全套深色令牌（bg `#0d1117` / panel `#161b22` / panel-2 `#1c2128` / border `#30363d` / text `#e6edf3` / muted `#8b949e`；accent 换青 `#00d4ff` + accent-dark `#00a8cc` + accent-dim `rgba(0,212,255,.12)`；danger/warn/ok/info 调亮适配深底 + 各自 dim 背景令牌）；`color-scheme: dark` 让原生下拉/滚动条随深色。散落硬编码浅色全部收进令牌：badge 五色、警告 banner、平台卡选中/禁用态、ref-pick 行 hover、topic-summary、warn-box 三色、item/decision/distill-progress、prog-badge、stepper dot、ref-files-modal、chip 两态。
- **JS 内联浅色兜底**：renderWarnings 直通提示 `style="background:#d1fae5"`（JS 不动）用 `.warn-box.ok { … !important }` 压成深色——唯一一处 JS 硬编码浅色，样式表覆盖后无残留。
- **字体**：JetBrains Mono 常规/粗体 woff2 下载后**以 base64 data URI 内联进 @font-face**（`data:font/woff2;base64,…`）——因后端无静态文件路由（仅 `/` 与 `/api/*`），`fonts/` 相对路径实测 404；经用户确认改内联方案（零网络请求、零外链、后端零改动）。界面中文保持系统字体栈未动。
- **控件自绘**：select（`appearance:none` + SVG data URI 箭头，`http%3A//` 编码不触外链 grep）、checkbox（自绘勾选）、radio（自绘圆点）、文件上传（`::file-selector-button` 自绘）、滚动条（`::-webkit-scrollbar` 4 段 + Firefox `scrollbar-width/scrollbar-color`）；焦点态统一青色描边 + 淡圈；autofill 深色兜底。
- **克制平面**：卡片细边框 + 微阴影、主按钮/进度条填充/stepper 完成态/选中态/链接走青色强调、placeholder/::selection 深色适配。
- **布局与 JS 零改动**：所有 grid 列宽（ref-pick 四列 / 三库表固定列宽）、table-layout、stepper 结构、class/id、SSE 解析等 JS 全部未动（`git diff` 变更行全部落在原 `<style>` 块内，逐行核对）。
- **自检**：`grep "https\?://"` 只剩两处 placeholder（`set-base-url` 默认值）；字体零外部请求（base64 内联）；`git status` 只出现 `static/index.html`（fonts 目录不入库）；pytest **1111 全绿** + `mypy src` 干净（33 文件）+ `node tests/js/sse-parser.test.mjs` 过。
- **服务已热载**：8000 端口在跑实例逐请求读盘，`curl /` 已含 data-URI 字体与深色令牌，浏览器刷新即可看效果（如需重启：桌面 firstep.lnk 或 `PYTHONPATH=src python -m contest_generator.webapp`）。

## 决策记录（grilling 2026-08-12，与用户逐条确认）

1. 范围：整个工具所有视图一次统一，不做局部试点
2. 痛点：太"程序员味"——默认浏览器控件、零设计感；无布局抱怨
3. 风格：深色科技感（IDE/终端风）
4. 深度：**只换皮**（颜色/字体/间距/圆角/阴影），布局结构、DOM、class/id 一律不动
5. 资源：**本地自托管**，不引任何 CDN（Google 系国内被墙；工具虽需联网调 DeepSeek，但静态资源不依赖外网）
6. 底色：近黑 `#0d1117`（GitHub Dark 风）
7. 强调色：青色系（`#00d4ff` 类）
8. 字体：只换代码块等宽字体为 JetBrains Mono（自托管 woff2，@font-face 本地相对路径）；界面中文保持系统字体栈（微软雅黑/苹方），**不自托管中文**
9. 控件：全自绘——select、checkbox、文件上传按钮、滚动条
10. 主题：只做深色单主题，不做浅色切换开关
11. 质感：克制平面——纯色卡片 + 细边框 + 青色点缀，无发光、无渐变炫技、无动效
12. 验收：用户浏览器人工过 8 步流程 + 7 tab + SSE 面板；pytest 全绿 + mypy src 干净（后端零改动应天然绿）

## 现状（已核实，探索 agent 2026-08-12）

- 单文件应用：`src/contest_generator/static/index.html`（2281 行；`<style>` 7-227 行约 220 行 CSS，JS 610-2281 行约 1670 行原生 JS，无框架）
- `:root` 已有 11 个设计令牌（9-12 行：`--bg #f5f6f8`、`--panel #ffffff`、`--border #dde1e6`、`--text #1c2530`、`--muted #6b7684`、`--accent #2563eb`、`--accent-dark #1d4ed8`、`--danger #dc2626`、`--warn #d97706`、`--ok #059669`、`--info #0891b2`），但**用得不彻底**：大量硬编码浅色散落（警告条 `#fef3c7`/`#f59e0b`/`#92400e` 49 行、选中平台卡 `#eff6ff` 53 行、badge 五色 56-62 行 `#fee2e2`/`#fef3c7`/`#e0f2fe`/`#e5e7eb`/`#d1fae5` 等）
- 深色已存在的锚点：代码块 `pre.result` `#0f172a` 底 + `#e2e8f0` 字（138 行）、弹层遮罩 `rgba(15,23,42,.5)`（202 行）
- 7 个导航 tab（`nav button` 切 `section.page.active`）：生成页 246-351（8 步卡片 + SSE 推荐面板 295-302）、模块库 354-392、参考文件库 395-459、PDF 资料库 462-479、赛题库 482-518、母版 521-585（stepper + SSE 提炼面板 536-562）、设置 588-607；另 ref-files-overlay 弹层由 JS 动态创建（1461 行）
- 零 CDN 零外部依赖；系统字体栈 `"Microsoft YaHei","PingFang SC"`（15 行）、等宽 Consolas；无 `@media` 无深色模式
- 状态色体系齐全：`.prog-bar` 轨/填充（180-182）、stepper 完成态 `--ok`（173-178）、`.primary` 主按钮（41-42）、badge（56-62）、警告 banner（49）

## 实施

1. **令牌层重构**：`:root` 全套令牌改深色语义（bg `#0d1117` 族、panel、border、text、muted；accent 换青 `#00d4ff` 类并配 dark/hover 变体；`--danger/--warn/--ok/--info` 调亮适配深底）；散落硬编码浅色全部收进令牌（badge 五色、警告条、选中态、hover 态、表格斑马纹）
2. **字体自托管**：JetBrains Mono 常规/粗体 woff2 下载后放 `src/contest_generator/static/fonts/`，`@font-face` 本地相对路径；应用到 `pre.result` 等等宽处；界面中文不动
3. **控件自绘**：select（`appearance:none` + 自绘箭头）、checkbox（自绘勾选）、文件上传按钮、滚动条（`::-webkit-scrollbar` 等）——深底下可读性优先
4. **克制平面打磨**：卡片细边框 + 微妙阴影、青色强调应用于主按钮/进度条填充/stepper 完成态/选中态/链接、间距圆角微调；**不动 grid/列宽/结构**
5. **JS 零改动**：只动 `<style>` 与 HTML 静态部分；class/id 结构保持（进度面板、弹层、stepper 全走既有类名）；勿动 `parseSSE` 等逻辑
6. **自检**：grep 确认无新增 `http(s)://` 外链；等宽字体请求落本地 static；`src` 目录外零改动

## 验收

- 用户浏览器人工过：8 步生成流程（含 SSE 推荐面板实时流）、7 个 tab 全部可读、ref-files 弹层、深色下控件自绘生效、无白底/浅色残留区块
- `pytest` 全绿（基线 1095+，后端零改动应无回归）+ `mypy src` 干净
- 自检：无外链资源、class/id 未改动、`git status` 只出现 `static/` 下文件

## 文件边界

`src/contest_generator/static/`（index.html + 新增 `fonts/` 目录）

**明确不动的：** 后端 Python 全部（webapp.py/generator.py 等）；JS 行为逻辑（SSE 解析、请求构造、DOM 操作）；布局结构/网格列宽/DOM class 结构；库数据与测试。
