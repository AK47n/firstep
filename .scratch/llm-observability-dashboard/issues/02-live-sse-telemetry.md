# 02 — SSE 流内实时 LLM 遥测

**要做什么：** 把收集器快照经既有 SSE 流浮出：推荐 / 骨架 / 修复 / 提炼的长任务进行中即展示 LLM 尝试次数、provider 拆分、重试/错误状态、总耗时、请求字节与可用时的 token 用量，同时保持现有 done / error 终态行为不变。

**被谁阻塞：** 01 — LLM 观测收集器接缝

**状态：** resolved

- [x] 至少一条高价值流（`/api/fix-errors` 或 `/api/recommend`）从收集器发射实时 LLM 遥测事件，且不改变既有终态事件。
- [x] 进度事件契约文档化新遥测事件字段，保持 content-safe。
- [x] 前端在流程期间渲染紧凑 LLM 状态行：总调用数、local/DeepSeek 计数、最新 operation、重试/错误种类、请求字节、耗时与可用时的 usage。
- [x] 遥测发射失败保持旁路，绝不使底层工作流失败。
- [x] 测试覆盖 SSE 事件形状与前端遥测行格式化。

## Notes

- `events.py` 新增 `llm_telemetry` SSE 事件字段，`llm_telemetry.py` 提供收集器快照 → content-safe 事件的适配器。
- `/api/fix-errors` 经适配器接线，不改现有 `done` / `error` 终态。
- 新增紧凑第 10 栏 LLM 遥测展示：调用数、provider 拆分、最新 operation、重试/错误计数、字节、耗时与数值型 usage。
- 领域文档补记新 LLM 遥测进度事件例外，SSE 测试验证脱敏。
- 验证：`python -m pytest`、`python -m mypy src`、`node --test tests/js/*.mjs`。
