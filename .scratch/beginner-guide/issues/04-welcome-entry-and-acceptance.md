# 04 — 欢迎卡「先看新手指引」入口 + 文档补一句 + 浏览器验收

**要做什么：** 首次打开（未配置 key 的 full 态）欢迎卡出现「先看新手指引」按钮，点击直接进入教程页——新手第一次打开就有两条路到教程（欢迎卡按钮 + 导航「指南」）。README 顺带提示入口；最后做浏览器验收。

**被谁阻塞：** 01 导航「指南」组 + 教程页骨架、02 教程内容「准备」+「做题主线」两章 + 页面渲染接入

**状态：** resolved

- [x] `static/js/fx/welcome.js`：`welcomeCardHTML('full')` 增加「先看新手指引」按钮（id=btn-welcome-guide，置于「去配置 API key」之前）；compact / hidden 态不含
- [x] `static/js/ui/welcome.js`：接线——点击 btn-welcome-guide 切到教程页（共用共享跳转 `gotoNavTab("guide")`，02 已抽 ui/nav-jump.js）
- [x] tests/js：`welcome.test.mjs` 更新——full 态含 `btn-welcome-guide` 且文案「先看新手指引」；compact / hidden 不含；全量绿（798）
- [x] README.md「然后呢：30 秒上手」补一句：第一次打开可先看顶部「指南 / 新手指引」（四章完整教程随时可回看）
- [x] 浏览器验收探针 `.scratch/beginner-guide/probe-04-entry.mjs`：模拟全新手（route 改写 /api/state api_configured=false）→ 欢迎卡 full 态含按钮 → 点击进入教程页 → 四章标题齐 → 跳转生效 → 导航三组 9 键回归 → 亮/暗主题截图 → 零 JS 错误；10 项全 PASS
- [x] 全量 tests/js（798）与 pytest（2827）无回归

### 评审记录（双轴，2026-08-30）

- **Standards**：硬违规 1 处已整改——新增行为缺 `beginner-guide/04` 工单行内注释（fx/welcome.js 按钮行、ui/welcome.js 接线、welcome.test.mjs 头注释）→ 已补；另修正 ui/welcome.js 既有块注释「共用同一跳转逻辑（去配 key）」不再统领 guide 按钮的注释漂移。判断项：按钮 `?.addEventListener` 重复 ×4 与 btn-welcome-* id 断言（既有风格，未改）。
- **Spec**：无 (a)/(b)/(c)——六项验收清单全部落实；唯一 nit（README 新增 bullet 与相邻 bullets 之间多一空行）已修。
- 验收：探针 probe-04-entry 10 项全 PASS（含 route 改写模拟全新手 full 态——本机已配 key 无法真实呈现 full，用 API 桩验证）；tests/js 798 通过、pytest 2827 通过。

### 特性全局验收（01-04 汇总）

- 导航第三组「指南 | 新手指引」（index.html）+ section#tab-guide 四子页签（准备/做题主线/编译与上板/交付与收尾）
- fx/guide.js 单源：GUIDE_TABS / GUIDE_CHAPTERS（四章中文教程正文）/ guidePanelFor / guideTabNext / guideBlockHTML / guideChapterHTML / guideBlocksOf + window 桥
- ui/guide.js 渲染 + 子页签点击/方向键切换（roving）+ 跳转按钮委托；ui/nav-jump.js gotoNavTab（欢迎卡/gen-banner/教程共用）
- 欢迎卡 full 态「先看新手指引」按钮；README 入口提示
- 测试：guide.test.mjs（纯函数 + HTML 契约）、guide-refs.test.mjs（内容守护：12 步表对应卡标题/AI 列口径/单源派生接线与产物 + 跳转目标 id）、nav-tabs-guard 三组 9 键、welcome.test.mjs、fx-guard 登记；探针 01-04 共 59 项全 PASS；tests/js 798、pytest 2827 全绿
