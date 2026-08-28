# 02 — 文档：CONTEXT.md 任务卡烧录词条 + 全量回归

**要做什么：** CONTEXT.md 的「任务推进」/「烧录」条目补一句：每张任务卡（已实现过的步骤）常驻烧录按钮（卡内独立状态/结果，条件 = taskCanFeedback 判据）；全量回归（pytest + JS + 语言/README/CHANGELOG 检查）。

**被谁阻塞：** 01 — 前端任务卡烧录按钮。

**状态：** resolved

- [x] CONTEXT.md：任务推进行补「每卡常驻烧录按钮（已实现过的步骤，卡内状态/结果，显示条件与上板反馈同判据）」；烧录词条补「任务卡入口」（前端三处入口：生成结果面板 + 任务执行结果面板 + 每张任务卡）。
- [x] 全量回归：pytest 全量 2646 passed（后端零改动）+ node --test tests/js/*.test.mjs 542 passed（含语言/README/CHANGELOG 检查在 pytest 全量内）。
- [x] 双轴 review + 提交（中文提交信息，git hooks 自动更新 CHANGELOG）。

**答复：** 已实现并合入（提交见 git log 任务卡烧录/02）。CONTEXT.md 两行更新 + 全量回归绿（pytest 2646 + JS 542）。
