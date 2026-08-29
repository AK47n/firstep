# 僵尸「进行中」恢复（工单 01：后端转移表 + 执行注册表 + 前端恢复按钮）

Status: resolved

## 背景

见 `.scratch/stuck-doing-recover/spec.md`。t1 磁盘 `doing` 0 轮 + 无按钮 + 状态机锁死 = 执行中断后的僵尸卡（用户实机 2024H 触发）。

## 改动清单

### task_progress.py
- `ALLOWED_STATUS_TRANSITIONS`（96-103）：`STATUS_DOING: frozenset({STATUS_PENDING})`。
- 表头注释（92-95）更新：doing 人工可恢复为 pending（执行中断出口）；doing→其余状态仍不可（无证据的跳过/验证/失败不做；退出终态仍由 run_task 回填）。
- `update_task_status` docstring（1197-1204）同步：去掉「doing 不可人工操作」的绝对表述，改为「doing 仅可恢复为 pending」。

### webapp.py
- 模块级 `_running_task_execs: set[str] = set()`（放在任务推进路由段之前的模块作用域，注释：进程内执行注册表——防「僵尸恢复」误伤真实执行中任务；单进程本地工具语义：进程活=执行真在跑，进程死=恢复安全）。
- `tasks_execute`（2069-2146）`run()` 闭包：`bind_llm_telemetry` 进 try 前 `_running_task_execs.add(task_id)`；`finally` 在 `add_completed` 旁 `_running_task_execs.discard(task_id)`。
- `tasks_status`（2336-2355）：output_dir 校验后、`apply_task_status` 前：`if task_id in _running_task_execs: raise TaskError("任务正在执行中，无法恢复——请等待完成（或重启服务终止旧执行）")`。docstring 补一句。
- `import time` 不需要（set 无时间戳）。

### static/js/fx/task.js
- `taskCardActions(status, opts)`（286-295）：`opts = opts || {}`；`case "doing": return opts.recoverable ? ["recover"] : [];`；docstring 更新（recover = 执行中断恢复为待做；仅 doing + recoverable 显示）。
- `taskCardActions` 注释「与后端 ALLOWED_STATUS_TRANSITIONS 镜像」保留（恢复通道两边同开）。

### static/js/ui/generate-tasks.js
- `tasksRender` actions 回调（161-204）：`const actions = taskCardActions(task.status, { recoverable: task.status === "doing" && !tasks.busy });`。
- `actions.includes("recover")` → `parts.push('<button class="btn-task-recover" data-task="' + esc(task.id) + '">已中断？恢复此步</button>')`（放在 run/skip 分支前或后均可，建议放在最前——doing 卡平时无其它按钮）。
- 新 `tasksRecover(taskId)`：`apiPost("/api/tasks/status", {output_dir: tasks.outputDir || reviseGetDir(), task_id: taskId, status: "pending"})` → `tasks.plan = data.plan` → `tasksRender()` → `toast("ok", "已恢复为待做——可重新点「做这一步」")`；catch → `toast("error", 错误信息)` + `await tasksReload()`（回填磁盘真相）。
- 事件委托：`.btn-task-recover` → `tasksRecover(btn.dataset.task)`（与 .btn-task-run 委托同区）。
- busy 守卫：恢复按钮仅在 `!tasks.busy` 时渲染（recoverable 已含），点击函数仍加 `if (tasks.busy) return;` 防御（与既有 runs 一致）。

### index.html
- 无改动（按钮由 actions 回调渲染，CSS 复用 .btn-task-* 基底即可——检查是否需要 .btn-task-recover 专属样式，若无视觉差异则不加）。

## 测试

### tests/js/task.test.mjs
- `taskCardActions("doing", { recoverable: true })` → `["recover"]`。
- `taskCardActions("doing")` → `[]`（既有断言兼容）。
- `taskCardActions("pending", { recoverable: true })` → `["run", "skip"]`（recoverable 不影响非 doing）。

### tests/test_task_progress.py
- `test_update_task_status_doing_recovers_to_pending`：构造 doing 任务 → apply_task_status(pending) 成功、任务 pending、清单落盘。
- `test_update_task_status_doing_rejects_other_targets`：doing → verified/unverified/failed/skipped 逐个 400（消息含「允许：pending」）。
- 既有 doing 断言（若存在「doing 不可操作」测试）更新为允许 pending。

### tests/test_webapp.py（或既有 tasks_status 端点测试文件）
- `test_tasks_status_rejects_running_task`：`_running_task_execs.add(task_id)` → POST /api/tasks/status pending → 400 消息含「正在执行中」；`discard` 后重试 → 200。
- `test_tasks_execute_registers_and_clears`：模拟 run 闭包（直接调用路由内 run 需要 SSE 桩——简化为验证注册表 add/discard 行为：monkeypatch run_task 抛异常，断言 finally 后 `_running_task_execs` 不含 task_id；成功路径同理）。

## 验收

- 后端全部测试绿 + JS 全量绿。
- 实机：重启 dev server（清注册表）→ 用户工程 t1 卡上出现「已中断？恢复此步」→ 点击 → t1 变 pending（toast）→ 「做这一步」按钮出现。
- 双轴评审通过后中文提交（spec/issues 随提，探针不提交）。

**收尾备注（2026-xx-xx）：** 本工单完成后未及时标记，状态改 resolved。实现提交：9a1c896（僵尸「进行中」恢复后端转移表 + 执行注册表 + 前端恢复按钮；文档回归 43d20b5）。
