# 02 — 教程内容「准备」+「做题主线」两章 + 页面渲染接入

**要做什么：** 教程页前两个子页签显示完整新手教程正文（从零讲起、面向第一次接触电赛/单片机的用户），正文里的「跳到功能」按钮可以点击并真实跳转到对应页签（去设置配 key、去生成等）。

**被谁阻塞：** 01 导航「指南」组 + 教程页骨架

**状态：** ready-for-agent

- [ ] `static/js/fx/guide.js`：前两章（准备 / 做题主线）教程数据 + HTML 渲染纯函数单源（章节标题、小节、正文段落、表格、「跳到功能」按钮数据），window 桥登记（沿用 fx 惯例）
- [ ] 「准备」章内容：四样东西（Windows 电脑 / Python 3.13+ / DeepSeek API key / 板子 + IDE）；如何安装（install.bat / start-app.vbs）；如何配 key；平台怎么选（STM32 vs MSPM0 一句话差异）；什么是 IDE / Keil / CCS 的人话解释
- [ ] 「做题主线」章内容：导航哪些 tab 是做题用的（生成 / 赛题库 / 设置）与资料管理 tab 的区别；12 步速览（步骤号与界面一致）；AI 边界——哪些步骤点按钮会调 DeepSeek（AI 推荐、骨架 main.c、编译修复、修订/深化、任务推进、参数速调咨询），与 `llm.py` `LOCAL_LLM_METHODS` 口径一致；第 11 步「任务推进」是写代码的主路径；第 12 步交接提示词的说明（工具内已有「和 AI 商量」）
- [ ] `static/js/ui/guide.js`：渲染教程页（#tab-guide 四面板）、四子页签点击切换、「跳到功能」按钮点击切 nav tab（参照 ui/welcome.js `gotoSettings` 模式，或抽出共享 `gotoNavTab`——实现时二选一并注明）
- [ ] index.html：module 区 import fx/guide.js + ui/guide.js、`initGuide()` 启动调用
- [ ] tests/js：新增 `fx/guide.test.mjs`（四章结构完整性、HTML 渲染关键锚点、转义——两章先就位，另两章章节标题按 03 再验）；新增内容守护测试（参照 glossary-refs.test.mjs 先例）钉「12 步」「任务推进」「新手词表」等与界面事实一致的词；`fx-guard.test.mjs` 登记 fx/guide
- [ ] 全量 tests/js 与 pytest 无回归
