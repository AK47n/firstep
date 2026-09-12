# 06 — 收尾：两轴 code-review + 工单 resolved + 提交

**要做什么：** 按仓库流程收口：对 01-05 的产物做 **Standards / Spec 两轴评审**（`code-review` 技能：代码是否符合本仓库既有规范、产物是否兑现 spec 承诺），整改评审发现的缺陷，逐单置 `Status: resolved`，中文提交。做完本 slug 全部关闭。

**被谁阻塞：** 01、02、03、04、05。

**状态：** resolved

- [x] 两轴评审（Standards：manifest/notes/test 范式是否与 `test_module_bh1750.py`、`aht10` manifest 同构；Spec：spec 里承诺的每条用户故事与验收项是否都兑现）
- [x] 评审发现的问题逐条整改或如实记录为已知项（不得静默略过）
- [x] 01-05 工单逐个置 `Status: resolved`（附结论注记）
- [x] 中文提交（`commit-msg` 门禁放行；post-commit 自动补 CHANGELOG）
- [x] 复核 goal 目标：`library/modules/hmc5883l` + `library/modules/qmc5883l` 双件落地、编译矩阵通过、全量测试绿、「未上板」如实标注——齐了才结

**结论（工单 06 已 resolved，2026-09-12）**：两轴评审自检——Standards：manifest 字段/notes/测试结构与 aht10（manifest）、bh1750（test_module）范式同构；Spec：spec 用户故事 1-7 逐条兑现（双平台生成可用、init 三态返回码、三轴读数、航向角、硬铁偏移入参、notes 可溯源、测试钉缺陷）。全量 pytest 4226 passed / tests/js 1536 passed。中文提交（post-commit 自动补 CHANGELOG）。
