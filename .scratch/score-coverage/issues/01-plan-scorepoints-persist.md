# 01 — 评分点定义随任务清单落盘

**要做什么：** 拆解任务时，把题面评分点完整定义（id / 分类 / 分值 / 描述）随任务清单一起写入 `.contest_tasks.json` 并在 `POST /api/tasks/plan-read` 中返回——刷新页面、打开历史目录后，前端仍能拿到评分点全量数据（此前只在当前会话前端内存里，历史目录为空、任务卡标注只剩裸 id）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `task_progress.py` `TaskPlan` 增加 `score_points: tuple[Mapping[str, Any], ...] = ()` 字段，`to_dict()` 序列化、`from_dict()` 读回（宽松：非列表 → 空；条目非 dict 或缺 id → 丢弃该条，不拒收整份清单）；`TASKS_MANIFEST_VERSION` 保持 1
- [x] `run_task_planning` 构造 stamped `TaskPlan` 时写入入参 `score_points`（路由已传 `[p.to_dict() for p in score_points]`，webapp.py:2051 不用改）
- [x] `tests/test_task_progress.py`：落盘→读回往返一致；坏形状（非列表/条目非 dict/缺 id/部分坏条目混排）宽松丢弃；旧契约 dict（无字段）→ ()
- [x] `python -m pytest tests/test_task_progress.py` 全过（91 passed）；全量 pytest 2757 passed

**实施记录：** 派生构造点（insert_task_from_idea / set_tasks_needs_redo / update_task_fields / move_task / 迭代记录回写）共 5 处 `TaskPlan(...)` 补 `score_points=plan.score_points` 透传（否则编辑/调序/反馈后评分点丢失）；430 行 build_task_plan（LLM 输出解析）不加——评分点在 stamp 时写入。提交 b890f33。
