# 僵尸「进行中」恢复（stuck-doing-recover）

## 问题陈述（用户实机反馈）

2024H 工程实测：t1（电机驱动与编码器采样）磁盘状态为 `doing` 且 **0 轮迭代**，任务卡显示「进行中」徽章、**没有任何操作按钮**——用户「不知道是卡住了还是啥的，按钮也没有」。t2/t3/t4 均已正常完成（各 1 轮迭代），证明用户被迫绕过 t1 继续执行。

根因（已取证）：
- `task_progress.py:96-103` `ALLOWED_STATUS_TRANSITIONS` 中 `STATUS_DOING: frozenset()`——doing **不可转移到任何状态**（注释「执行中，退出终态由 run_task 回填」）。
- `run_task`（task_progress.py:819-969）只在 **LLM 调用段**（892-915 的 try）有失败恢复 `previous_status`；「备份→写盘→编译验证→状态回填」（918-968）之间若进程被杀 / 服务重启 / 停电，磁盘永久停在 doing。
- `fx/task.js:286-295` `taskCardActions("doing")` 返回 `[]`——前端无按钮。
- webapp 日志只有 3 条完成的 `POST /api/tasks/execute`（t2/t3/t4），t1 的执行发生在旧进程（dev server 22:33:51 重启过）——执行随进程被杀而中断，状态未落盘。

**后果**：任何执行中断（服务重启 / 断电 / 进程被杀 / 客户端断流后服务端也死）都会产生一个无出口的僵尸卡：状态机锁死 + 前端无按钮 + 用户只能手动改 JSON 或重拆清单（丢失全部进度）。

## 目标

1. 为用户提供**「执行中断？恢复此步」**按钮：doing 且当前无活跃执行时，一键把任务恢复为 `pending`（回到可执行状态，进度与轮次历史全保留）。
2. **防护误恢复**：若该任务**真的正在执行**（服务端进程内注册表），拒绝恢复并提示「正在执行中」——防止把正在跑的任务改回 pending 后并发双写 main.c。
3. 恢复只改状态，不动 main.c / 备份 / 轮次（备份链完整，重做可回滚）。

## 用户故事

1. 我在任务卡看到「进行中」但没有任何按钮，点「已中断？恢复此步」→ 卡变「待做」，出现「做这一步」按钮，继续正常推进。
2. 我误以为卡住了、其实服务端还在跑（刷新页面后 SSE 断）→ 点恢复被拒：「任务正在执行中，无法恢复——请等待完成」。
3. 恢复不丢进度：已有轮次历史、备份、对话结论、资源标注全部保留；恢复后重做 = 新一轮（新增备份）。
4. 恢复后的卡若代码其实已实现（僵尸执行可能已写盘 main.c），我可以选择「跳过」（计入进度）或「做这一步」（重做，备份可回滚）。

## 实现决策

### 后端
1. `STATUS_DOING` 转移表改为 `frozenset({STATUS_PENDING})`（task_progress.py:102；注释更新：doing 人工可恢复为 pending——执行中断出口；doing→其他状态仍不可，无证据的跳过/验证/失败不做）。`update_task_status` 的错误消息「无（执行中不可操作）」路径不再被 doing 触发，但保留兜底。
2. **进程内执行注册表**（webapp.py 模块级）：`_running_task_execs: set[str] = set()`。
   - `tasks_execute` 的 `run()` 闭包：进入 `bind_llm_telemetry` 前 `_running_task_execs.add(task_id)`，`finally`（现有 `context.recent_llm_workflows.add_completed(collector)` 旁）`discard(task_id)`——执行完成/失败/进程内异常都清理。
   - `tasks_status`：`output_dir` 校验后加 `if task_id in _running_task_execs: raise TaskError("任务正在执行中，无法恢复——请等待完成（或重启服务终止旧执行）")`（任何改标都拒，不只 pendegin——正在跑的卡不该被人工改标）。
   - 单进程本地工具的语义：服务进程活着 = 注册表无残留 = 恢复安全；进程已死 = 注册表没了 = 恢复直接成功。客户端断流不影响（服务端继续跑完）。
3. 不做：服务启动时自动清理孤儿 doing（多实例风险 + 「doing 只能由执行设置」不保证未来语义）；不做 doing→failed/unverified 通道（恢复为 pending 后用户可用既有「跳过/做这一步/确认通过」走全语义）。

### 前端
4. `fx/task.js` `taskCardActions(status, opts)`：加第二参数 `opts.recoverable`（布尔，默认 false）；`doing` 且 recoverable → `["recover"]`（其余状态忽略该参数，行为不变）。签名变更向后兼容（现有调用只传 status）。
5. `ui/generate-tasks.js` `tasksRender` 的 actions 回调：`taskCardActions(task.status, { recoverable: task.status === "doing" && !tasks.busy })`；`actions.includes("recover")` → push `btn-task-recover` 按钮（文案「已中断？恢复此步」，data-task）。
6. 新 `tasksRecover(taskId)`：`POST /api/tasks/status {output_dir, task_id, status: "pending"}`（复用既有端点，多一轮转移表校验）→ 成功 `tasks.plan = data.plan` → `tasksRender()` → toast「已恢复为待做——可重新点『做这一步』」；失败（如 400 正在执行中 / 清单未拆解）→ toast error + `await tasksReload()` 回填磁盘真相。同步小调用，不设 SSE。
7. 委托：网格容器事件委托加 `.btn-task-recover` 分支。
8. 卡上提示：doing + recoverable 时按钮文案自带「已中断？」语义，不再另加徽章文字（保持卡面干净）。

### 测试
9. 后端：转移表 doing→pending 允许 / doing→verified|unverified|failed|skipped 仍拒（apply_task_status 400）；注册表占用时 tasks_status 400（消息含「正在执行中」）、执行完任务后注册表已清（模拟 run 函数 finally 语义用直接 add/discard 测路由层判断）。
10. JS：`taskCardActions("doing", {recoverable:true})` → `["recover"]`；`taskCardActions("doing")` 仍 `[]`；其余状态带 recoverable 参数行为不变。

## 范围外
- 服务启动自动清理孤儿 doing。
- doing→failed / doing→unverified 人工通道。
- 恢复按钮的确认弹窗（恢复无破坏性：只改状态，main.c 与备份不动；后端注册表已挡真实执行中误点）。
- 多进程 / 多实例执行的注册表一致性。

## 交付
- `.scratch/stuck-doing-recover/issues/01-backend-frontend-recover.md`（后端转移表 + 注册表 + 前端按钮 + 测试）
- `.scratch/stuck-doing-recover/issues/02-docs-regression.md`（CONTEXT.md 词条 + 全量回归）
