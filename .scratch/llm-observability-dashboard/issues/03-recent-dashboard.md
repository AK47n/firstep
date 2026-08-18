# 03 — 最近 LLM 工作流仪表盘

**要做什么：** 加一个轻量的设置页/仪表盘面板：基于内存「最近工作流」ring buffer，让已完成的推荐 / 骨架 / 修复 / 提炼运行在流结束后仍可查看。

**被谁阻塞：** 01 — LLM 观测收集器接缝；02 — SSE 流内实时 LLM 遥测

**状态：** resolved

- [x] Completed workflow summaries are stored in an in-memory bounded ring buffer and are not written to config or disk.
- [x] A read-only endpoint returns recent workflow summaries and sanitized per-call details.
- [x] Settings or a dedicated dashboard card displays recent workflows with provider split, call count, total duration, request bytes, statuses, and token usage when present.
- [x] UI clearly labels token/usage as provider-reported and does not estimate currency cost.
- [x] Tests cover ring-buffer truncation, endpoint redaction, and frontend rendering of summary/detail rows.

## Notes

- Added `llm_recent_workflows.py` (`LLMRecentWorkflowStore`): thread-safe, memory-only deque(maxlen=20) of `LLMWorkflowSnapshot`; snapshots come from the sanitized collector and keep only `_CALL_FIELDS` + `sanitize_llm_usage`, so no prompt / response / key / file content leaves the seam.
- Wired `add_completed(collector)` via `try/finally` into recommend / skeleton / fix-errors / masters-distill / masters-confirm routes so even failing runs show up (status=error); archive route brought in line with the streaming routes.
- Added read-only `GET /api/llm-workflows/recent`（设置节，`@_map_errors`）；不写 config / 磁盘。
- Settings 页新增「最近 LLM 工作流」卡片：summary 行（名称 + 状态、call 数、local/DeepSeek 拆分、请求字节、总耗时、usage）+ 每次调用明细行；脚注明确「token 数为模型服务商上报（provider-reported），本工具不估算费用」「仅保存在内存，重启即清空」；切到设置页签自动加载 + 刷新按钮。
- Added `tests/test_llm_recent_workflows.py`（ring buffer 截断、content-safe summary/details）、`test_webapp.py` endpoint 用例（fix 流结束后断言脱敏 + usage 聚合）、`tests/js/recent-workflows-format.test.mjs`（summary/detail 行格式化 + 脚注文案）。
- Fixed a test-file defect left mid-edit: the previous session's insert had swallowed the `def` line of `test_fix_errors_unsafe_fix_path_ends_with_error_event`, merging its body into the new test (FileExistsError on `_fix_project`); restored the `def`.
- Verified with `python -m pytest`, `python -m mypy src`, and `node --test tests/js/*.mjs`.
