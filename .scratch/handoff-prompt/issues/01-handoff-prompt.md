# 01 — 交接提示词（Handoff）栏 + 历年真题汇总 PDF 链接（未提交改动补单）

**What to build:** 两个已写入 `src/contest_generator/static/index.html` 工作区、但无工单/未验证/未提交的前端功能（**后端零改动**）：

1. **生成页第 9 栏「交接提示词（Handoff）」**：把赛题原文 / 平台 / 模块清单（含简介与依赖）/ main.c 骨架 / 输出目录与结构 / 手动勾选参考资料打包成一段完整提示词（HTML 结构 + `btn-handoff`/`btn-handoff-copy` + `handoffModuleLines`/`handoffPlatformLabel`/`handoffPlatformIde`/`handoffReferenceLines` 四个 helper），一键生成 + 复制，供用户粘贴给下一个 AI 会话做精准打磨（本工具只搭基础，精打磨在下一个会话完成）。
2. **赛题库页顶部「历年真题汇总（2017-2025）」链接**：`loadTopicArchiveLink()` 经 `/api/pdfs?name=000_2017-2025` 素材库定位（批次目录变动也能命中），`window.open` 浏览器原生预览；素材库缺失/查询失败静默不显示。

**Status:** resolved（2026-08-12 补单验证闭环，待提交）

## 现状（2026-08-12 核查）

- `git status` 仅有 `src/contest_generator/static/index.html` 一个文件、143 行新增（+143，无删除），`origin/main` 已是最新（3f07e24 已推送）。
- 引用符号自检全过：`expanded`/`selectedSlugs`/`chosenPlatform`/`state.platforms`/`selectedReferenceIds`/`apiGet`/`pdfFileUrl`/`esc`/`$("problem")`/`topic-summary-box`/`main-c`/`res-dir`/`res-structure` 均已有定义。
- 未跑 pytest/mypy，未做浏览器验收。

## 验收记录（2026-08-12）

- [x] pytest **1111 全绿**（21.23s，后端零改动天然绿）+ `mypy src` 干净（33 文件）
- [x] `node --check` 内嵌 JS 语法校验过
- [x] `git status` 只有 `static/index.html` + 本工单文件（引用符号自检全过，见现状）
- [x] 用户浏览器人工验收（2026-08-12）：生成页第 9 栏可生成/复制提示词；赛题库页顶部出链接、点击可预览 PDF

## 验收标准

- [x] pytest 全绿 + `mypy src` 干净（后端零改动应天然绿）
- [x] `node --check` 语法校验（或等价）过
- [x] `git status` 只出现 `static/index.html` + 本工单文件
- [ ] （可选，浏览器人工）生成页第 9 栏可生成/复制提示词；赛题库页顶部出链接、点击可预览 PDF
