# 01 — LLM 观测收集器接缝

**要做什么：** 一个小而安全的观测收集器接口：一次逻辑工作流可收集脱敏的 LLM 调用记录（含本地/远程 RoutingLLM 调用与预算耗尽未发送的失败），不暴露 prompt / 响应 / 密钥，也不让 llm.py 依赖 SSE 或 UI。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] 工作流级收集器按 workflow id + 单调递增 sequence 记录脱敏调用观测。
- [x] 既有日志观测保持脱敏保证：不含 prompt、响应、API key、源文件内容或编译输出。
- [x] 网络发送前的预算耗尽产生 not_sent 观测（error_kind=`budget`）。
- [x] RoutingLLM 同工作流内的本地 + 远程调用共享同一收集器 / workflow id。
- [x] 单测覆盖聚合字段、脱敏、预算耗尽捕获与本地/远程关联。

## Notes

- 实现 `LLMObservationCollector` / `LLMCallObservation`：workflow id + 单调 sequence，保留脱敏日志发射。
- 补发送前预算耗尽观测（`parse_status=not_sent`、`error_kind=budget`）。
- web 路由层把同一个收集器贯穿本地 + 远程 `RoutingLLM` 工作流构造。
- 经 `mattpocock-skills:code-review` 评审；修正实例级 workflow id 与结构化脱敏断言。
- 验证：`python -m pytest`、`python -m mypy src`、`node --test`。
