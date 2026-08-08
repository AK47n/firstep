# 05 — 赛题库管理 UI（浏览 / 拆条录入 / 删除）

**What to build:** 赛题库页签（样式沿用参考文件库页签，PR #10 已立样板）：浏览列表 + 搜索、长 PDF 拆条录入（含逐条校对）、删除单条。后端补两个薄路由：`GET /api/topics`（列表，现只有单条 `GET /api/topics/{key}`——工单 01 没做列表）与 `DELETE /api/topics/{key}`（删除，工单 01 没有删除能力）；topic_library.py 补 `list_topics` / `delete_topic`（删除 = 条目目录移除，参考 reference_library.delete_reference 模式）。拆条录入流程依赖工单 04 的分块拆条。

**参考文件库 UI 已完成（PR #10，不用重做）**：参考文件库页签 = 三路搜索（标题/类型/锚定）+ 录入表单（文件文本区 + AI 简介草稿 + 锚定二选一 + kit 词表下拉）+ 删除确认；提炼报告判定加"归档为该题参考文件"按钮（载荷 `{path, topic, reason}` 透传）。本工单只做赛题库侧，风格保持一致。

**页面内容：**
- 浏览：按 年份 / 编号 过滤的列表（题面预览截断显示）；每条显示关联模块（复用 `discover_related_modules`，API 已有 related_modules 字段）；
- 拆条录入：上传长 PDF → 拆条（工单 04）→ **逐条校对表**（年份 / 题号 / 题面文本框可改，可删条目）→ 确认入库（`POST /api/topics/confirm`，multipart：pdf + payload JSON）；校对是工单 01 设计的核心环节，必须可改可删、确认前不落盘；
- 删除：确认对话框后删条目目录；
- 错误信息沿用现有 error 风格（400 中文原样显示）。

**测试：** 后端薄路由 + list/delete 用现有 topic_library 测试风格（假库目录）；前端浏览器自验（起独立端口实例，参考 PR #10 验收方式）；真机：现有 8 条题库（2018C/2019A/2020C/2021F/2022C/2022H/2024H/2026C）浏览可见、2026C 命中、删除一条再补回（确认不留脏数据）。

**Blocked by:** 04 — 拆条分块（录入流程的前置）；01 — 赛题库录入后端（已有）

**Status:** open

## Comments

（待实施后补）
