# 02 — 步骤 8「编辑 main.c」精确入口 + guide 文案修正

**要做什么：** 步骤 8 工具栏新增「编辑 main.c」按钮（在代码 tab 打开 main.c 并聚焦编辑），「查看工程」保留；新手指南与第 8 步联动描述改为与实际一致。

**被谁阻塞：** 01（打开桥 filePath 能力）。

**状态：** resolved

- [x] 步骤 8 工具栏新增「编辑 main.c」按钮（title 说明直接打开 main.c 编辑）
- [x] 点击 → 代码 tab 激活 + main.c 标签打开且为活动标签；「查看工程」仍开整个目录
- [x] guide 代码栏章节「与第 8 步联动」条目改为与实现一致（「编辑 main.c」直接打开；「查看工程」打开整个目录）
- [x] 冒烟：smoke-02.mjs 全绿（btn-edit-mainc → activePath === "main.c"；查看工程仅开目录）

## Answer

- 已验证：smoke-02.mjs 5 项全绿；guide 文案与实现一致（「编辑 main.c」直接打开 main.c）。
