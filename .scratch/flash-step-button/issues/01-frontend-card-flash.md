# 01 — 前端：任务卡烧录按钮（每步常驻入口 + 卡内独立状态/结果）

**要做什么：** 每张任务卡（已实现过的步骤：执行过至少一轮或已终态）在操作行前常驻「烧录到板子」控制行；点按后卡内展开「烧录中…」状态位与结果行/指引卡；每卡独立容器（uid = task.id），与执行结果面板的烧录行（uid = "result"）并存不冲突。

**被谁阻塞：** 无（后端 /api/flash 已有，flash-deploy 已合入）。

**状态：** resolved

- [x] fx/flash.js `flashPanelHTML(dir, uid)` 加 uid 参数：容器 id = `tasks-flash-status-<uid>` / `tasks-flash-result-<uid>`，按钮 `data-task-flash="<uid>"` + `data-dir`；缺省 uid = `"result"`（任务执行结果面板既有调用不传，形状兼容）；**评审整改：id 契约与缺省 uid 抽 `flashContainer(uid)` 单源**（producer 渲染与 consumer 定位共用，防两端手写漂移被 `!statusEl` 静默吞掉；DOMAINS + 单测登记）。
- [x] fx/task.js `taskCardHTML` 在操作行前插入 `flashPanelHTML(o.outputDir, task.id)`（仅当 `o.outputDir` 且 `task.id` 且 `taskCanFeedback(task)`——显示条件单源复用「上板反馈」判据：非 doing 且有迭代记录或已终态；pending/skipped/doing 不显示，防烧旧固件；`task.id` 假值不渲染 = spec 轴评审 (c)1 防御：裸空 id 会令 flashContainer 缺省降成 "result" 撞结果面板容器）；`tasksGridHTML` 透传 `opts.outputDir`。
- [x] ui/generate-tasks.js `tasksRender` 传 `outputDir: tasks.outputDir`（tasksGridHTML opts）；「烧录到板子」委托改读 `data-task-flash`（uid）+ `data-dir` → `tasksFlash(uid, dir)`；`tasksFlash` 按 `flashContainer(uid)` 定位卡内状态/结果元素，缺省 `"result"`；结果面板烧录行保留（uid 缺省 = "result"）；委托注释修正「实时值」→「渲染时快照」= spec 轴评审 (b)2。
- [x] tests/js/flash.test.mjs flashPanelHTML 参数化断言（id 含 uid / data-task-flash / 缺省 uid）+ flashContainer 契约单测；tests/js/task.test.mjs taskCardHTML 集成断言（outputDir + 已实现状态 → 含烧录控制行；pending/doing/无 outputDir → 无）。
- [x] JS 全量测试绿（542）+ 双轴 review + 整改复核。

**答复：** 已实现并合入（提交见 git log 任务卡烧录/01）。整改说明（双轴评审）：standards 无硬违规；最重判断项「uid 容器 id 契约双处手写、漂移被静默吞掉」→ 抽 fx/flash.js `flashContainer(uid)` 单源（flashPanelHTML 与 tasksFlash 共用，DOMAINS + 单测登记）；其余判断项（哨兵字符串单点化、data-task-flash 命名——spec 契约保留、task.js 跨域 import——可辩护取舍）不整改。spec 轴全验收点通过；(c)1 task.id 假值防御已整改；(c)2「skipped 不显示」依赖隐式不变量（状态机 skip 仅出自 pending，pending 无迭代）当前正确、记录在案不整改。JS 542 / pytest 2646 全绿。
