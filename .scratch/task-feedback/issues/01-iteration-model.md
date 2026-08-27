# 工单 01：迭代历史数据模型（TaskIteration + Task.iterations）

**要做什么：**
- `task_progress.py` 新增 `TaskIteration`（frozen dataclass：seq/kind/feedback/status/backup_id/compile_summary/at）与 `Task.iterations: tuple[TaskIteration, ...] = ()`。
- `Task.to_dict/from_dict` 带出/读回 iterations（旧清单无该字段 → 缺省空元组，向后兼容；单条形状非法 → 忽略该条不报错）。
- `run_task` 执行完成后向任务追加一条迭代记录（kind="execute"，feedback=当时 note 或空，status=终态，backup_id=本轮备份，compile_summary=编译摘要，at=时间戳）并落盘；`_with_task_status` 兼容带 iterations 的 Task 重建。
- 每次执行前把任务当前 iterations 原样带入新 Task（不丢历史）。

**被谁阻塞：** 无（task-progress 已 resolve）。

**状态：** resolved（双轴评审通过 + 整改：Standards ① _iter_opt_str 抽取（_parse_iterations 五字段重复）；Spec (c) previous_status 捕获提前修复 + 回归测试）

## 验收标准

- [x] tests/test_task_progress.py：初始执行后任务带 1 条迭代记录（字段全、kind=execute、status=终态、backup_id 非空）
- [x] 再次执行（反馈/重做）追加而非覆盖，seq 递增
- [x] 旧 shape 清单（无 iterations）读回正常，iterations=()
- [x] 单条 iteration 形状非法（缺字段/非 dict）不报错、被忽略
- [x] 全量 pytest 无回归（含既有 32 条 task_progress 测试）
