## Problem Statement

LLM 链路已经有本地/远程路由、请求体预算、RetryBudget 与结构化观测，但这些事实主要停在服务端日志和测试里。用户在推荐、骨架、提炼、修复循环中仍只能看到“AI 正在…”这类粗粒度状态，不知道本轮实际走本地还是 DeepSeek、请求重试了几次、是否遇到 429/5xx/解析失败、请求体距离预算还有多近、一次工作流到底花了多少次 LLM 调用。结果是：省钱/提速优化无法量化，retry budget 的价值不可见，出慢/贵/失败时也难定位是哪一段调用导致。

## Solution

做一个轻量的 LLM 成本/耗时仪表盘：把现有 `llm_observation` 结构化观测从“只进日志”升级为“工作流内可收集、SSE 可展示、设置页可查看最近记录”的统一观察面。

第一步只展示已有事实，不改 prompt、不改 local/remote 路由策略、不引入 token 估价表。仪表盘要能回答：本次工作流调用了几次 LLM、local/DeepSeek 各几次、总耗时、请求字节、重试/解析失败/429/5xx/预算拦截次数，以及每次调用的 operation/provider/model/status/parse_status/error_kind/duration_ms/request_bytes/usage。

## User Stories

1. As a user running recommendation, I want to see whether calls used local or DeepSeek, so that I can verify本地路由是否真省钱。
2. As a user waiting on a slow LLM step, I want retry/backoff and attempt counts surfaced, so that I know it is still progressing rather than卡死。
3. As a user debugging 502 failures, I want error_kind and parse_status surfaced, so that I can tell network/rate-limit/parse/client/budget failures apart.
4. As a user tuning request size, I want request_bytes shown per call and aggregated per workflow, so that I can identify which path is close to the 128KB guard.
5. As a user using fix loop, I want each compile-fix batch to show LLM call count and total duration, so that “继续修复” cost is visible before I keep spending calls.
6. As a maintainer, I want observations collected through a small interface, so that llm.py does not grow UI/SSE knowledge and tests can exercise the same seam.
7. As a maintainer, I want budget-exhausted/not-sent observations captured, so that RetryBudget failures are not invisible in logs or UI.
8. As a maintainer, I want local and remote calls in a RoutingLLM workflow to share one workflow id, so that duplicate per-instance call_id values do not confuse tracing.
9. As a maintainer, I want no prompt text, response body, API key, source content, or compile log content in observations, so that telemetry remains safe to display.
10. As a maintainer, I want the dashboard to be optional presentation over existing behavior, so that failures in telemetry collection never break generation or repair.

## Implementation Decisions

- Add a deep observation module with a small interface: a per-workflow collector object accepts sanitized LLM observation records and returns snapshots/summary; llm.py only emits sanitized records to the collector, not to webapp/front-end concepts.
- Preserve the existing server log observation shape as the base record; add workflow/run id and monotonic sequence where needed so local/remote RoutingLLM calls can be correlated even when each DeepSeekLLM instance has its own call_id.
- Keep the interface content-only-safe: operation, provider/route, model, duration_ms, attempts, status, final, call_id, workflow sequence, budget_attempt, http_status, error_kind, parse_status, request_bytes, usage numeric fields only.
- Capture budget exhaustion before send as a not_sent observation when RetryBudget stops a request before `_chat_once` builds/records a normal result.
- Surface live telemetry through existing SSE flows as progress events rather than a new polling dependency for recommendation/skeleton/fix/distill; failures to emit telemetry stay旁路.
- Add a settings/dashboard view that shows recent completed workflow summaries from an in-memory ring buffer; no persistence in config.json and no secrets stored.
- Pricing is explicitly out of the first slice unless token usage is already present; show token counts/request bytes and leave currency estimation for a later ticket.

## Testing Decisions

- Unit-test the observation collector as the primary seam: redaction, aggregation, ring-buffer behavior, workflow id/sequence, and budget-exhausted capture.
- Test DeepSeekLLM emission with fake transports and injected collector; assert existing logging remains content-redacted.
- Test RoutingLLM correlation: one logical workflow with local + remote calls yields one workflow id and monotonic sequence despite separate underlying clients.
- Test SSE contract at one high-value route first (`/api/fix-errors` or `/api/recommend`): telemetry events are emitted and do not change existing terminal done/error behavior.
- Test front-end formatting with node tests for summary rows and detail rows; do not rely on browser screenshots for the first slice.

## Out of Scope

- Changing prompts, retry counts, backoff policy, local method set, or DeepSeek/local routing decisions.
- Adding token pricing tables or currency cost estimates.
- Persisting telemetry across app restarts.
- Sending telemetry to any external service.
- Reworking compile_runner output size or fixing unrelated duplicate DOM ids.
- Refactoring all retry loops into one primitive.

## Further Notes

Architecture review candidates that led here:

- True bug / visibility gap: RetryBudget defaults are uncapped in normal webapp flows, and budget exhaustion before send currently has no observation record.
- Cost/time improvement: local/remote route choice and retry counts are already known but not user-visible, so users cannot tell whether local routing is paying off.
- Speed/cost improvement: request_bytes and usage already exist in observation records; surfacing them gives immediate feedback without changing prompts.
- Just cleanliness: the retry policy still exists in several loops, but a broad retry-runner refactor is lower ROI than first making current behavior visible.
