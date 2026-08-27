# 02 — 单任务执行

**要做什么：** 学生点任务卡「做这一步」（可先在补充框里给一句说明）→ 工具调 LLM 产出实现该任务后的 main.c 全文 → 写盘前整树备份 → 编译验证闭环（绿 = verified；无工具链 = unverified 大声降级；修一轮仍红 = failed）→ 前端结果面板展示确定性 diff + 状态 + 报错摘要；支持一键回滚到本任务执行前。执行前服务端现读 main.c（手工编辑保留）。

**被谁阻塞：** 01（任务清单已存在，按 task_id 执行）

**状态：** resolved

**评审记录**（code-review 双轴，fixed point = ae16bdc）：Standards 判零硬伤（尾段抽取 verify_compile_tail 逐字节保留原行为、事件序/降级载荷/修复轮语义全齐）；修复的判断项 —— ① `reviseRenderDeepenDiff` 复用泄漏「深化」文案 → 参数化 entity（任务面板显示「任务未改动…」）；② 状态徽章 if/else 在深化/任务两处逐字复制 → 抽 fx/task.js `verifyStatusMarkup` 单源（两面板共用）；③ `_main_diff` 兼容别名 → 迁移 test_deepen.py 导入后删除。Spec 判 3 条 —— ① note 不落盘（spec 用户故事 10「备注」）→ `_with_task_status(note=...)` 执行后持久化 + 测试；② message 深化措辞泄漏 → `verify_compile_tail(subject="任务结果")` + `_status_message(subject)` 参数化，任务载荷现为「任务结果已标记…」；③ 前端「回滚按钮」只有文字说明 → 结果面板真按钮（复用 /api/revise/rollback 同备份族）+ 新增 `/api/tasks/plan-read` 读端点（回滚后重读清单）+ tasksReload。另修：LLM 空结果失败路径恢复 previous 状态（不钉死在 doing）+ 测试。

**验收：** 全部 ✓；测试 test_task_progress.py（01+02 共 23 条）+ 全量 2521 通过；mypy 0 错；JS 485 通过。

- [ ] 抽公共尾段：`resolve_compile_toolchain → compile → 失败 run_fix_round 修一轮 → 重编译 → 状态判定` 抽成 `deepen.py` 内公共函数（或新模块），`run_deepen` 与 `run_task` 共用，行为逐字节不变（回归测试守）
- [ ] LLM 协议新增 `execute_task(main_c, task, note, module_interfaces, problem_text, qa_text) -> str`（输出 = 实现后 main.c 全文；DeepSeek + RoutingLLM + 测试假 LLM；空结果 = TaskError）
- [ ] `run_task` 域编排：读任务 → `emit(task_executing)` → LLM → 整树备份（复用 revision.backup_tree + revise_backup_root，回滚入口与深化一致）→ 写盘 → 确定性 diff（复用 deepen._main_diff 或抽公共）→ 编译验证闭环 → 状态回填 `.contest_tasks.json`（doing → verified / unverified / failed）→ done 载荷（形状同深化尾段）
- [ ] `POST /api/tasks/execute`（SSE）：`{output_dir, task_id, note?}`；事件 `task_executing`（events.py 词表新增）→ compile_start → fix_start（仅首轮失败）→ verify_result → done；回滚复用 `/api/revise/rollback` 通道
- [ ] 前端：任务卡「做这一步」按钮 + 可留空补充框 + 执行结果面板（diff / 状态 / 报错摘要，照深化结果面板先例）+ 回滚按钮，纯函数入 fx
- [ ] 测试：假 LLM 整文件输出 → 写盘逐字节断言；备份存在；编译三态（内存目录 + 假编译，照 test_deepen.py）；note 进 prompt（假 LLM 捕获断言）；diff 正确性
