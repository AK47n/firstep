# 03 — 任务状态管理

**要做什么：** 学生可跳过不打算做的任务（skipped）、把已验证任务改回待做（pending 重做，必要时先回滚）、把上板确认过的任务人工标「已验证」（verified——主要是 verify=manual 任务与无工具链的 unverified 结果）；任务清单落盘实时更新，隔天 / 历史目录入口继续推进进度不丢；修订执行（模块集变化重生成）后任务清单自动作废（删文件 + 前端提示重新拆解）。

**被谁阻塞：** 01（任务清单与状态词表已存在）

**状态：** resolved

**评审记录**（code-review 双轴，fixed point = ca9af18）：Standards 无硬伤；修 4 项判断项 —— ① unverified 徽章按 status 硬编码「无工具链降级」，manual 验收降级后徽章误导 → 后端下发 `verify_cause: "manual"` + verifyStatusMarkup 按 cause 分徽章；② 转移图在 JS 双处重编码（显隐 if/else + 按钮三元）→ 抽 fx/task.js `taskCardActions` 单源 + 单测；③ status 路由在 route 内读-验-写 → 抽域编排 `apply_task_status`（薄壳回归）；④ tasks-invalidated 重置漏清陈旧结果面板 + 未比对目录 → 补 stale 清理 + dir 守卫。Spec 无阻塞；修 1 项 —— 前端「显隐」无测试（内联闭包）→ taskCardActions 纯函数化 + 断言（镜像后端转移表）。判定保留：状态机表只建模人工改标子集（run_task 直写 doing→终态，域内不合法值不可达，设计注释）；status 端点返回 {task, plan}（plan 未用但为进度刷新留口）；修订作废 = 存在性标记 + rmtree 清文件（.bak 同样被清，可接受机制偏差）。

**验收：** 全部 ✓；测试 test_task_progress.py（01-03 共 39 条）+ 全量 2530+ passed；mypy 0 错（changed 5 文件）；JS 487 通过。

- [ ] 状态机纯函数：合法转移表（pending → doing → verified/unverified/failed/skipped；verified → pending 重做；unverified/failed → verified 人工改标；skipped → pending 恢复），非法转移拒绝（如 pending 直接 verified 未被 AI 执行过 = 拒绝或允许？——按用户拍板「人工可改标」允许 unverified/failed → verified 直达，其余非法 400 中文）
- [ ] `POST /api/tasks/status`（同步 JSON）：`{output_dir, task_id, status}` 改标 + 落盘 + 返回最新任务
- [ ] 修订联动：`/api/revise/apply` 执行后（模块集变化路径）删除 `.contest_tasks.json`（force 已备案档则顺带删 .bak），done 载荷带 `tasks_invalidated: true`
- [ ] 前端：任务卡跳过 / 重做 / 人工改标按钮（按当前状态显隐）+ 修订执行后的「任务清单已作废，请重新拆解」提示条
- [ ] 测试：状态机转移表全覆盖（合法 + 非法）；改标落盘 roundtrip；修订执行后文件删除断言；前端纯函数文案/显隐
