# 02 — 教程内容「准备」+「做题主线」两章 + 页面渲染接入

**要做什么：** 教程页前两个子页签显示完整新手教程正文（从零讲起、面向第一次接触电赛/单片机的用户），正文里的「跳到功能」按钮可以点击并真实跳转到对应页签（去设置配 key、去生成等）。

**被谁阻塞：** 01 导航「指南」组 + 教程页骨架

**状态：** resolved

- [x] `static/js/fx/guide.js`：前两章（准备 / 做题主线）教程数据 + HTML 渲染纯函数单源（章节标题、小节、正文段落、表格、「跳到功能」按钮数据），window 桥登记（沿用 fx 惯例）
- [x] 「准备」章内容：四样东西（Windows 电脑 / Python 3.13+ / DeepSeek API key / 板子 + IDE）；如何安装（install.bat / start-app.vbs）；如何配 key；平台怎么选（STM32 vs MSPM0 一句话差异）；什么是 IDE / Keil / CCS 的人话解释
- [x] 「做题主线」章内容：导航哪些 tab 是做题用的（生成 / 赛题库 / 设置）与资料管理 tab 的区别；12 步速览（步骤号与界面一致）；AI 边界——哪些步骤点按钮会调 DeepSeek（AI 推荐、骨架 main.c、编译修复、修订/深化、任务推进、参数速调咨询），与 `llm.py` `LOCAL_LLM_METHODS` 口径一致；第 11 步「任务推进」是写代码的主路径；第 12 步交接提示词的说明（工具内已有「和 AI 商量」）
- [x] `static/js/ui/guide.js`：渲染教程页（#tab-guide 四面板）、四子页签点击切换、「跳到功能」按钮点击切 nav tab（抽出共享 `gotoNavTab`（ui/nav-jump.js），welcome 同步改用——评审归一）
- [x] index.html：module 区 import fx/guide.js + ui/guide.js、`initGuide()` 启动调用（01 已有，02 增正文 CSS）
- [x] tests/js：`fx/guide.test.mjs`（章节结构/块字段合法性/渲染锚点/转义/guideBlocksOf）、`guide-refs.test.mjs` 内容守护（12 步表逐行对应卡标题 + AI 列口径 + 跳转目标 id 存在）、`fx-guard.test.mjs` 登记 fx/guide
- [x] 全量 tests/js（796）与 pytest（2827）无回归

### 评审记录（双轴，2026-08-30）

- **Standards**：无硬违规（分层/单源/桥/import 方向/注释工单号/CSS 令牌全合规）。判断项 2 条已整改：①`guideBlockHTML` note 分支 `role="note"` 死分支（全部 note 数据均带 label，Speculative Generality）→ 移除；②块遍历逻辑在三处重复（渲染/校验/文案提取各自嵌套遍历，Repeated Switches）→ fx/guide.js 增 `guideBlocksOf` 扁平遍历单源，两测试改用它。接受项：.guide-tab 胶囊样式与 .revise-tab 近似（仓库既有三处先例，01 评审已记录待统一）。
- **Spec**：3 处事实不符已整改：①「检查环境」在设置页不存在（实际按钮为「一键体检」、卡片为「环境体检」）→ 文案改正；②「一键补齐」按钮在生成页就绪总览而非设置页 → 语境迁移（新增「就绪总览与一键补齐」提醒块）；③AI 边界精度——11 步表与「key 的边界」提示补充「个别小操作（模块简介校验、推荐澄清）配本地 Ollama 可离线」。另按 spec.md:47 强化：内容守护新增 12 步表 AI 列逐行钉住（2/4 本地、5/8 要 AI、9/12 不用、10 双口径）。范围蔓延：welcome.js 改走共享 gotoNavTab 为 02 工单授权选型（评审归一），非蔓延。
- 验收：探针 `.scratch/beginner-guide/probe-02-content.mjs` 12 项全 PASS（两章正文渲染/12 步表/跳转实际生效/后两章占位/零 JS 错误）；tests/js 796 通过、pytest 2827 通过。
