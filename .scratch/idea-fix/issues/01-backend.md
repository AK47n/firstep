# 工单 01：灵活修正后端（llm / task_progress / webapp / events + 测试）

Status: resolved

## 目标

实现 spec（.scratch/idea-fix/spec.md）后端全链路：
`analyze_idea`（分类：new_task / direct_fix / discussion）→ `insert_task_from_idea` / `run_direct_fix`（备份 + 写盘 + 编译验证 + 回滚）→ `mark_tasks_needs_redo` 落盘。

## 交付

- llm.py：IdeaAnalysis @dataclass + Protocol.analyze_idea / apply_idea_fix + TASK_IDEA_SYSTEM_PROMPT + _idea_user_prompt + _idea_fix_user_prompt + DeepSeek 实现（json_mode / 文本 _retry_parse）+ RoutingLLM passthrough（remote）。
- task_progress.py：Task.needs_redo（缺省 False 兼容旧清单）+ insert_task_from_idea + mark_tasks_needs_redo + run_direct_fix（备份 → apply_idea_fix → 写盘 → main_diff → verify_compile_tail(subject="修正结果")；不造 TaskIteration；LLM 空结果 TaskError）。
- events.py：EVENT_IDEA_ANALYZING（idea_analyzing → idea_result → done）。
- webapp.py：POST /api/tasks/idea/analyze（SSE）/ insert（同步）/ fix（SSE，复用 compile/verify 事件词表，done 含 affected）/ mark-redo（同步）。
- tests/fakes.py：FakeLLM / RecordingLLM 加两方法。
- 测试：llm / task_progress / webapp 新用例 + fakes 增量；全量 pytest 绿。

## 验收

1. `/api/tasks/idea/analyze` 返回分类与建议；kind 非法 → LLMError 重试后 500（或 400，按既有 LLMError 处理）。
2. `/api/tasks/idea/insert` 落盘后 plan 含新任务且旧任务不动；.bak 先备份。
3. `/api/tasks/idea/fix` SSE 序列 = idea 之前无新事件，执行期 compile_start / fix_start / verify_result / task_reporting / done；done 载荷 {status, backup_id, compile, main_diff, message, affected}；受影响任务 needs_redo=true 落盘。
4. run_direct_fix：备份存在可回滚（/api/revise/rollback 复用）；无工具链 → unverified 降级；修一轮仍红 → failed。
5. 旧 .contest_tasks.json（无 needs_redo 字段）读取 → 全部 false。
6. 全量 pytest 绿（既有 2646 + 新增）。
