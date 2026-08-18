# 02 — Live LLM telemetry in SSE flows

**What to build:** surface collector snapshots through existing SSE flows so long-running recommendation/skeleton/fix/distill work shows LLM attempts, provider split, retry/error status, total duration, request bytes, and token usage when available, while preserving current done/error terminal behavior.

**Blocked by:** 01 — LLM observation collector seam

**Status:** resolved

- [x] At least one high-value flow (`/api/fix-errors` or `/api/recommend`) emits live LLM telemetry events from the collector without changing existing terminal events.
- [x] The progress event contract documents the new telemetry event fields and remains content-safe.
- [x] Frontend renders a compact LLM status row during the flow: total calls, local/DeepSeek counts, latest operation, retry/error kind, request bytes, duration, and usage if present.
- [x] Telemetry emission failures stay旁路 and never fail the underlying workflow.
- [x] Tests cover SSE event shape and frontend formatting for the telemetry row.

## Notes

- Added `llm_telemetry` SSE event fields in `events.py` and a `llm_telemetry.py` adapter that converts collector snapshots into content-safe events.
- Wired `/api/fix-errors` through the adapter without changing existing `done` / `error` terminal behavior.
- Added compact 第 10 栏 LLM telemetry display, including calls, provider split, latest operation, retry/error counters, bytes, duration, and numeric usage.
- Updated domain docs for the new LLM telemetry progress event exception and verified redaction in SSE tests.
- Verified with `python -m pytest`, `python -m mypy src`, and `node --test tests/js/*.mjs`.