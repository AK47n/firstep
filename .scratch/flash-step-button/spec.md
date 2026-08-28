# 任务卡烧录（flash-step-button）Spec

## 问题陈述

逐步深化（任务推进）的「烧录到板子」按钮目前只在两处：生成结果面板、任务执行结果面板（`tasksRenderResult` 插入，网格重渲染即清除）。用户每次做完一步想上板检测，必须赶在结果面板还在时点，或回到生成面板——**每一步没有常驻烧录入口**，不符合「每一步上板检测」的使用节奏。

## 目标

每张任务卡（已实现过的步骤）常驻「烧录到板子」按钮：做完一步 → 编译验证 → 卡上直接烧录 → 上板观察 → （不符再点「上板反馈」）。烧录中状态与结果行**在卡内展开**（每卡独立的「烧录中…」状态位 + 结果行/指引卡），不依赖会被重渲染清掉的结果面板。

## 用户故事

1. 作为学生，完成某一步（编译绿/未验证/失败均可）后，该任务卡上有「烧录到板子」按钮，点击即烧（无需回到结果面板或生成面板）。
2. 烧录中卡内显示「烧录中…（探针，请确认连接，勿拔线）」；成功后卡内显示 ✓ 已烧录（工具 + 固件 + 输出明细 + 复制命令）；失败显示 ✗ + 排查提示 + 输出明细；工具/产物缺失显示指引卡（安装说明 + 设置页跳转）。
3. 未实现过的步骤（待做/已跳过）不显示按钮——防止烧到上一个任务的旧固件误判；执行中的步骤（doing）不显示（防并发）。
4. 与执行结果面板的烧录按钮并存不冲突（各自独立状态位，任意入口点击都可用）。

## 实现决策

- **显示条件单源 = `fx/task.js` `taskCanFeedback`**（非 doing 且已有迭代记录或已终态 = 有可观察产物，与上板反馈同判据）；`pending`/`skipped`/`doing` 不显示。
- **卡内元素参数化**：`fx/flash.js` `flashPanelHTML(dir, uid)` 加 uid 参数（容器 id = `tasks-flash-status-<uid>` / `tasks-flash-result-<uid>`，按钮 `data-task-flash="<uid>"` + `data-dir`）——多卡并存不冲突；缺省 uid = `"result"`（任务结果面板既有调用兼容）。
- **任务卡集成**：`fx/task.js` `taskCardHTML` 在操作行前插入 `flashPanelHTML(o.outputDir, task.id)`（仅当 `o.outputDir` 且 `taskCanFeedback(task)`）；`tasksGridHTML(plan, opts)` 透传 `opts.outputDir`（`ui/generate-tasks.js tasksRender` 传 `tasks.outputDir`）。
- **委托**：`ui/generate-tasks.js` tasks-grid 既有点击委托 `.btn-task-flash` 改读 `data-task-flash`（uid）+ `data-dir` → `tasksFlash(uid, dir)`；`tasksFlash` 按 uid 定位卡内状态/结果元素（`$("tasks-flash-status-" + uid)`）；结果面板烧录行保留（uid = `"result"`，dir 取渲染时快照）。
- **busy 防重**：沿用 `tasks.busy` 全局闸 + `flashRunShared` 共享执行体（ui/flash.js，零后端改动）。
- 后端零改动（`POST /api/flash` 现有契约不变）。
- 范围外：不做「每步自动烧录」；不动生成结果面板按钮。

## 测试决策

- `tests/js/flash.test.mjs`：`flashPanelHTML` uid 参数化（id 含 uid / 空 dir 空串 / 缺省 uid 兼容）。
- `tests/js/task.test.mjs`：`taskCardHTML` 集成（opts.outputDir + 已实现状态 → 卡含烧录控制行；pending/无 outputDir → 无；不做显示条件重复断言——taskCanFeedback 既有测试已覆盖）。
- 全量 JS 540+ 绿；pytest 全量（后端零改动，回归确认）；双轴 review。
