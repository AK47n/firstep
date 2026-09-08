# 06 — 布局调整：顶栏工具栏移除（代码区视觉重心上移，状态指示并入底部状态条）

> 注：本文件为工单 06 补记（实现与提交已完成：commit 801f65ce；当时工作记录
> 未单独落盘，此处分录保持工单档案完整）。用户原话：「这一栏可以换个地方吗
> 不要放在顶上，看起来整体代码视觉偏下」。

**要做什么：** 「代码」tab 顶部工具栏（目录信息条 + 操作按钮行）整体移除，
改由底部 .code-statusbar 状态条承接目录提示与「去生成页编辑 main.c」入口；
代码区自标签条顶开始，视觉重心回到代码本身。

**被谁阻塞：** 无（独立小改）。

**状态：** resolved

**实现笔记：** 顶部 .code-toolbar 删除（目录 label / 按钮全部移入底部
.code-statusbar：code-dir-label + btn-code-goto-generate，isMainCDiskDir
谓词与 updateGotoGenerateVisibility 随迁）；CSS 同步清理；nav data-tab=code
title 与空态文案微调；冒烟 smoke-05 新增布局断言（.code-toolbar 不存在 +
状态条目录提示）。

- [x] 顶栏移除：代码区自 tab 条开始，无标题行/按钮行残留。
- [x] 目录提示与「去生成页编辑 main.c」按钮迁入底部 .code-statusbar。
- [x] 布局断言入 smoke-05；全量回归绿。
