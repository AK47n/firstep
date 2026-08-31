# 02 — 5 个写盘入口接线 + CDP 冒烟

**要做什么：** 在 startFixCenter（btn-fix-center）、reviseApply（btn-revise-apply）、reviseDeepen（btn-revise-deepen）、任务「做这一步」taskRun（.btn-task-run 委托）、参数「改值并编译」paramsApply（.btn-params-apply 委托）五个动作函数开头 await guardCodeTabWrite(动作中文名)，取消则中止并 toast；入库 .scratch/code-write-guard/smoke.mjs（CDP 探针：同目录+脏标签 → 弹确认 → 保存继续 true / 取消 false / 无脏直通）。

**被谁阻塞：** 01（守卫模块可用）。

**状态：** resolved

- [x] 验收 1：5 个入口均已接线（动作函数开头 await guard，取消 → 中止 + toast 中文，不发起请求——CDP 断言 fetch 计数为 0）。
- [x] 验收 2：只读动作（分析/扫描/规划/会话/聊天）不接线（回归不弹窗）。
- [x] 验收 3：smoke.mjs 全 PASS：确认路径（保存落盘、脏点清除、返回 true）、取消路径（返回 false、脏点保留）、无脏直通（true）、非上下文目录直通（true）。
- [x] 验收 4：回归——node 全量 + pytest 全量 + smoke-02~05 全绿；提交/工单/CHANGELOG 中文。

**结论（2026-08-31）：** 全部落地并提交。评审整改：①continueFixCenter「继续修复」补 guard（WG.continueFix，复用修复路径同样被保护）；②任务执行全部写盘路径统一收敛到 tasksExecute 内部 guard（feedback 非空 = WG.taskFeedback「按反馈修复」，否则 = WG.task「做这一步」——上板反馈复用路径不再遗漏；委托分支原 guard 移除防双弹）；③reviseApply guard 移至「确认执行修订」modal 之前（防双模态倒序）；④startFixCenter guard 移至 outputDir/platform/toolchain 校验之后（无输出目录/无工具链时零打扰）；⑤smoke 补「非上下文 + 脏 → 直通 true 零弹窗零保存」用例。接线 7 处全部使用 WRITE_GUARD_ACTIONS 单源。冒烟 11 项 PASS（原 10 + 非上下文 1）；回归——node 1006 全绿、pytest 3049 全绿、smoke-02~05 全绿。
