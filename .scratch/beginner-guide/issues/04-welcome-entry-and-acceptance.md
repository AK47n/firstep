# 04 — 欢迎卡「先看新手指引」入口 + 文档补一句 + 浏览器验收

**要做什么：** 首次打开（未配置 key 的 full 态）欢迎卡出现「先看新手指引」按钮，点击直接进入教程页——新手第一次打开就有两条路到教程（欢迎卡按钮 + 导航「指南」）。README 顺带提示入口；最后做浏览器验收。

**被谁阻塞：** 01 导航「指南」组 + 教程页骨架、02 教程内容「准备」+「做题主线」两章 + 页面渲染接入

**状态：** ready-for-agent

- [ ] `static/js/fx/welcome.js`：`welcomeCardHTML('full')` 增加「先看新手指引」按钮（id=btn-welcome-guide，文案确定）；compact / hidden 态不含
- [ ] `static/js/ui/welcome.js`：接线——点击 btn-welcome-guide 切换到教程页（复用/共享 gotoNavTab 或与 02 同一模式；若 02 已抽共享跳转函数则改用之）
- [ ] tests/js：`welcome.test.mjs` 更新——full 态含 `btn-welcome-guide` 且文案「先看新手指引」；compact / hidden 不含；全量绿
- [ ] README.md「然后呢：30 秒上手」补一句：首次打开可先看顶部「指南 / 新手指引」
- [ ] 浏览器验收探针（.scratch/beginner-guide/probe-*.mjs 惯例）：导航三组渲染、「新手指引」进入、四子页签切换、欢迎卡按钮跳转、亮/暗主题截图无破版；不引入新端到端框架
- [ ] 全量 tests/js 与 pytest 无回归
