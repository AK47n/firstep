# 03 — 任务状态管理

**要做什么：** 学生可跳过不打算做的任务（skipped）、把已验证任务改回待做（pending 重做，必要时先回滚）、把上板确认过的任务人工标「已验证」（verified——主要是 verify=manual 任务与无工具链的 unverified 结果）；任务清单落盘实时更新，隔天 / 历史目录入口继续推进进度不丢；修订执行（模块集变化重生成）后任务清单自动作废（删文件 + 前端提示重新拆解）。

**被谁阻塞：** 01（任务清单与状态词表已存在）

**状态：** ready-for-agent

- [ ] 状态机纯函数：合法转移表（pending → doing → verified/unverified/failed/skipped；verified → pending 重做；unverified/failed → verified 人工改标；skipped → pending 恢复），非法转移拒绝（如 pending 直接 verified 未被 AI 执行过 = 拒绝或允许？——按用户拍板「人工可改标」允许 unverified/failed → verified 直达，其余非法 400 中文）
- [ ] `POST /api/tasks/status`（同步 JSON）：`{output_dir, task_id, status}` 改标 + 落盘 + 返回最新任务
- [ ] 修订联动：`/api/revise/apply` 执行后（模块集变化路径）删除 `.contest_tasks.json`（force 已备案档则顺带删 .bak），done 载荷带 `tasks_invalidated: true`
- [ ] 前端：任务卡跳过 / 重做 / 人工改标按钮（按当前状态显隐）+ 修订执行后的「任务清单已作废，请重新拆解」提示条
- [ ] 测试：状态机转移表全覆盖（合法 + 非法）；改标落盘 roundtrip；修订执行后文件删除断言；前端纯函数文案/显隐
