# 01 — LLM observation collector seam

**What to build:** a small, safe observation collector interface that lets one logical workflow collect sanitized LLM call records, including local/remote RoutingLLM calls and budget-exhausted not-sent failures, without exposing prompts/responses/secrets and without coupling llm.py to SSE or UI.

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] A workflow-scoped collector records sanitized call observations with workflow id and monotonic sequence.
- [x] Existing log observations keep their redaction guarantees and do not include prompt, response, API key, source file content, or compile output.
- [x] Budget exhaustion before network send produces a not_sent observation with error_kind `budget`.
- [x] RoutingLLM local + remote calls in one workflow share the same collector/workflow id.
- [x] Unit tests cover aggregation fields, redaction, budget-exhausted capture, and local/remote correlation.

## Notes

- Built `LLMObservationCollector` / `LLMCallObservation` with workflow id + monotonic sequence and retained redacted log emission.
- Added pre-send budget exhaustion observations (`parse_status=not_sent`, `error_kind=budget`).
- Threaded one collector through local + remote `RoutingLLM` workflow construction in the web routes.
- Reviewed with `mattpocock-skills:code-review`; fixed instance workflow ids and structured redaction assertions.
- Verified with `python -m pytest`, `python -m mypy src`, and `node --test`.
