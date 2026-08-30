# 验收走查报告 — ux-walkthrough-02（用户体验优化一期，A–Q 全包）

- 走查基线：`main @ 02befbee`（chore: 自动更新 CHANGELOG），24 个工单全部 `状态：resolved`
- 走查日期：2026-08-29（会话内完成）
- 环境：webapp 8000（python 3.14.6，`PYTHONPATH=src python -m contest_generator.webapp`）+ Chrome headless CDP 9251
- 结论：**验收通过，无需补票**；仅一处工单书面对账差异已当场修正（见 4）

## 1. 探针复核（前端无回归）

### probe-02.mjs（工单 02：6.5 多实例卡纳入步骤体系）——通过，jsErrors: none
实况轨迹（stm32 平台 + led/key 模块）：

| 阶段 | 导航点 | 徽章 | 步骤 7 | 6.5 卡 |
|---|---|---|---|---|
| 初始 | 12 点无 ✓，chip 6.5(h) | 隐藏 | 未就绪 | 隐藏 |
| led 展开（3 实例） | 3✓ 6✓ 6.5✓ 7✓ | 隐藏 | ✓ | 可见 |
| 清空实例 | 6✓ 6.5(无✓) 7✓ | 「还差 1 个实例」 | ✓ | 可见 |
| 加回 1 实例 | 6.5✓ 7✓ | 隐藏 | ✓ | 可见 |
| led+key 混合清空 | 6✓ 6.5 7(无✓) | 「还差 2 个实例」 | 未就绪 | 可见 |

- 「还差 N 个实例」徽章 / 6.5 导航点 / 总览 chip 显隐全部符合工单 02 口径（计数单源 `instanceGapCount`，`src/contest_generator/static/js/fx/module.js:335`）。
- 步骤 7 语义复核：判定单源 `step7DoneState`（`src/contest_generator/static/js/fx/draft.js:107`）= 平台已选且已展开且（无引脚角色 | 已绑定 | 多实例已配引脚 | 已按默认布线生成）。stm32-led 无 `pins` 声明（默认 PC13/14/15 在 pin_config.h），故清空实例后 roles 为空 → 步骤 7 仍 ✓（「无角色无需配置」分支），与工单 02「与角色绑定路径一致」一致；stm32-key 有 `gpio_in KEY_START 必接 默认 PB3` 角色 → 清空实例后步骤 7 正确翻转为未就绪。属设计内行为，非回归。

### probe-narrow.mjs（工单 24：窄屏响应式）——通过
- 生成页 900×800 / 720×900：`scrollWidth == clientWidth`，溢出元素 0 个。
- 补测设置页（probe-narrow-settings.mjs，同口径）：900×800 / 720×900 均无溢出。
- 宽屏 1920×1080（probe-23-24.mjs 复核工单 24 验收项 3）：生成页/设置页均无溢出；页面 JS 异常 0。

## 2. 回归套件

- 前端：`node --test "tests/js/*.test.mjs"` → **917 通过 / 0 失败**（含 welcome / welcome-responsive / ai-entries / library-polish / pdf-library / reference-library / topic-browser 等 22/23/24 相关守卫）。
- 后端：`python -m pytest tests -q` → **2905 通过**（3 条既有告警：StarletteDeprecationWarning httpx→httpx2；test_fix_errors.py 的 `\m`/`\p` SyntaxWarning，均非本次引入）。

## 3. 工单状态与验收清单核对

- 24 个工单 `状态：resolved` 全部就位；01–21 验收框已全勾且与实现一致（抽查 02 行为经探针逐条复核）。
- **发现对账差异**：工单 22 / 23 / 24 虽为 resolved，验收框全为未勾（实现与测试早已落地：提交 4765e1dc、123b404e、628f9ceb、ce60c2ef 等）。

## 4. 当场修正：22/23/24 验收框补勾（逐项验证后）

- **22（O 库页面小修）**：参考/PDF 默认排序 = mtime 降序（DOM 实况 `#ref-sort`=mtime「按最近更新（默认）」、「↓ 降序（默认）」；`#pdf-sort`=mtime「按修改时间（默认）」）；赛题/PDF 读取失败清占位同位置错误（`js/ui/topic.js:310-315`、`js/ui/pdf.js:259-264`）；赛题库占位延迟 150ms（`js/ui/topic.js:294-302`）；库目录卡 5 目录（`index.html:3098-3109`）——模块/母版为可编辑 INPUT，赛题/参考/PDF 为只读 SPAN 派生值，说明文字「派生目录（只读，跟随模块库目录）」实况存在；改模块库目录确认联动（`js/ui/settings.js:397-407`，取消≠失败见 :500）。
- **23（P 「和 AI 聊」入口收敛）**：3 处「有问题？去问 AI」直达按钮实况存在（修复中心 `index.html:2433` / 修订执行 `:2531` / 母版页 `:2935`，均 `data-goto-global-chat`）；入口定位说明齐备——每卡「本卡只聊这一步；工程级疑问用「全局商量（工程级）」」（`fx/task.js:522`）、全局商量（`index.html:2572-2573`）、参数速调（`:2621-2622`）、买件商量「本区只谈选型与买件；…全局商量（工程级）」（`fx/recommend.js:206`）、第 12 步交接提示词呼应（`index.html:2654` + `fx/guide.js:216,237,432`）；`ai-entries.test.mjs` 通过。
- **24（Q 欢迎卡 + 窄屏）**：compact 态真实渲染验证（页内经 `import('/js/app.js')` setState api_configured=true 后重跑 `initWelcome`）→ 渲染「开始做题」「打开新手指引」两按钮，点「开始做题」→ 切生成页并聚焦 `#problem`；两档窄屏无溢出（探针）；宽屏无回归（探针）；`welcome.test.mjs` / `welcome-responsive.test.mjs` 通过。

修正后：24 工单 status=resolved 且验收框 100% 勾选（5/5、5/5、4/4…合计 118 框全勾）。

## 5. 新问题与观察（均未追票）

- **无功能回归、无新问题需补票。**
- 观察（仅开发侧，不影响产品）：spec 测试决策记载的回归命令 `node --test tests/js`（目录形式）在本机 Node v24.15.0 报 `Cannot find module ...\tests\js`，需改用 `node --test "tests/js/*.test.mjs"`（已用该形式跑通 917 用例）。未追票原因：属文档/环境口径问题，非 UX spec 范围；如需要可另行开一票统一修正命令写法。
- 工作树在走查前已有与本批次无关的未提交改动（`library/references/2026_07_电赛带练真题资料/` 下 2 个文件被修改、大量 .scratch 未跟踪文件），本走查未触碰。

## 6. 走查产物（.scratch/ux-walkthrough-02/ 下新增）

- `accept_count.py`：工单验收框勾选统计（UTF-8 直读）。
- `diag-probe02-state.mjs`：probe-02 后平台/角色/步骤状态诊断。
- `probe-narrow-settings.mjs`：设置页窄屏溢出补测（probe-narrow 同口径）。
- `probe-23-24.mjs`：22/23/24 验收项 DOM 实况 + 宽屏复核。
- `diag-libdir-note.mjs`：派生目录说明文字复核。
