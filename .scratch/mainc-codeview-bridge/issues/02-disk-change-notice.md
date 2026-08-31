# 02 — 任务 / 深化 / 修订后的磁盘更新提示

**要做什么：** 第 11 步任务每步成功、深化完成、修订应用之后，自动对磁盘 main.c 与步骤 8 编辑框做一次差异检测：内容一致 = 静默（不打扰）；内容不一致 = 状态行升级为警示「磁盘 main.c 已更新 → [加载]」，用户点一下才覆盖编辑框——任何情况下不自动覆盖用户的手动编辑。

**被谁阻塞：** 01（状态行与重新加载机制）。

**状态：** resolved

- [x] 执行一步确实改写 main.c 的任务成功后，回到步骤 8 能看到「磁盘 main.c 已更新 → [加载]」警示行。
- [x] 点击「加载」→ 编辑框显示任务产物，状态恢复「已同步」；行号 / 高亮 / 草稿同步。
- [x] 任务失败（status=failed）或未改写 main.c → 无提示，编辑框不被覆盖。
- [x] 深化完成、修订应用成功后走同一检测路径（同一语义：不同才提示）。
- [x] 检测复用只读文件端点，不新增写侧；事件驱动、不轮询。

## 实现说明

- 钩子点（均为 done 终态后、fire-and-forget 同一条 refreshMainCDiskState 路径）：
  - 任务执行成功分支（generate-tasks.js：data.status !== "failed" 时 markStepDone(11) 后）；
  - 修订应用完成（generate-revise.js reviseApply：reviseRenderApplyDone 后）；
  - 深化完成（generate-revise.js reviseRunDeepen：reviseRenderVerify 后，含失败轮——失败也可能改过磁盘，检测不打扰仅在差异时提示）；
  - 参数速调应用 / 回滚（params.js：写盘路径后——spec 问题陈述将「参数修改」列为事实分裂来源，超出工单验收清单的钩子，按 spec 问题陈述补齐）。
- 一致性分支（一致 → 静默 synced；差异 → changed 警示；读失败 → 静默保留现状）均属工单 01 交付的 refreshMainCDiskState，02 零新纯函数。
- 踩坑记录：clear-jargon-guard 守卫静态断言源码不含「写盘」（用户可见文案防行话），注释中该词也会触发——改用「写入磁盘」。
- 验证：changed 端到端 by smoke-02.mjs（7 项：synced → 外部改写 → changed 警示 + 编辑框不被自动覆盖 → 点击加载恢复 synced）；node --test 963 全绿。
