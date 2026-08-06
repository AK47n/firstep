# 02 — 提炼端点改 SSE 流：进度事件 + 完整报告随流返回

**What to build:** `/api/masters/distill` 从"同步 POST → JSON 响应"改为 SSE 流（text/event-stream）。后端把工单 01 的发射器接到流上：`start` → 事件… → `done`（携带完整提炼报告，与现状响应同构）或 `error`（中文错误信息）→ 流结束。HTTP 状态 200 起流，失败以流内 `error` 事件收尾（客户端只认事件，不依赖状态码）。

要点：

- 报告必须随流返回：提炼确认前不落任何东西、服务端无状态，没有二次查询的可能（spec「传输」）
- 错误映射复用现有 `_error_response` 语义：`LLMError` → 502 中文 message、业务失败 → 400——但都作为流内 `error` 事件发出，而不是 HTTP 非 200
- 扫描 / 对比 / 拼装报告是瞬间步骤，不发事件，直接以 start（带总量）开头、done 收尾
- 断线（客户端关闭）时后端正常结束本次提炼（确认前不落任何东西，无副作用）
- 前端不接（工单 03）；本工单只保证流契约与测试

**Blocked by:** 01

**Status:** open

**Reference:** `.scratch/distill-progress/spec.md`（Implementation Decisions「传输」「事件契约」、Testing Decisions）、`docs/adr/0004`、CONTEXT.md「进度事件」词条
