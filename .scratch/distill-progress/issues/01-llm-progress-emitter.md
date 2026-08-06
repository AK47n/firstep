# 01 — LLM 层进度发射器：提炼事件的唯一出处

**What to build:** 母版提炼的进度事件从 LLM 层发出（spec「发射 seam」）。`distill_master` 入口增加可选进度发射器参数（默认 None——不接不影响行为，测试假 LLM 与真 LLM 走同一参数），发射点在批次循环层。事件契约的唯一出处在此（spec「事件契约」，ADR 0004）。

事件类型与字段（唯一出处，契约测试断言）：

- `start`：总量——待判文件数、阶段 1 批数（由 `_judgment_batches` 先算定）、阶段 2 批数（⌈待判文件数 / 批大小⌉，也先算定）
- `batch_start`：阶段、批号、批总数、该批文件路径清单（阶段 1 = 待判文件路径；阶段 2 = 摘要路径）
- `batch_done`：阶段、批号、已处理文件数
- `retry`：阶段、批号、补问轮次、缺失数（`_summarize_batch` / `_decide_batch` 的补问循环每次开始补问轮时发射）
- `phase_done`：阶段、文件数
- `done` / `error`：由 webapp 层（工单 02）发射——本工单只管到 phase_done 为止的进度事件，不碰报告
- 批数为 0（全部文件都是规则处理的残留 / 二进制等）时不发射任何批事件，阶段直接完成

发射点：`_summarize_judgment_files`（阶段 1：start 由入口发、批循环层发 batch_start / batch_done、结束发 phase_done）、`_decide_distillation`（阶段 2 同款）。发射器调用失败不影响提炼主流程（发射是旁路，不因 UI 消费失败中断提炼——或直接透传，二选一，实现时选并注明理由）。

**Blocked by:** 无

**Status:** resolved

**Reference:** `.scratch/distill-progress/spec.md`（Implementation Decisions「发射 seam」「事件契约」）、`docs/adr/0004`

## Comments

- 2026-08-06 工单 01 完成合入 main。实现：`llm.py` 新增事件契约（`ProgressEvent`
  frozen dataclass + 事件 / 阶段常量，唯一出处，契约测试断言）+ 发射 seam
  （`distill_master` 可选 `progress_emitter`，默认 None 不发射——不接不影响行为；
  LLM Protocol 与 FakeLLM 走同一参数）。
- 发射点：start 由入口发射，阶段 1 批数 = `_judgment_batches` 先算定、阶段 2
  批数 = ⌈待判文件数 / 批大小⌉ 同样先算定，算定的批序列直接传给阶段循环——
  start 的总量与实发批序列严格一致；批循环层发 batch_start（带批文件路径清单：
  阶段 1 = 待判文件路径、阶段 2 = 摘要路径）/ batch_done（本阶段累计已处理文件
  数，前端直接显示"已读 X/115"）/ retry（补问轮开始发，轮次 1 起、缺失数）；
  两阶段结束发 phase_done。批数为 0 不发射任何批事件、阶段直接完成。
- 决策（spec「发射 seam」二选一）：发射器调用失败 = 旁路吞掉，不中断提炼——
  理由：主产物是 10-15 分钟 API 调用换来的完整报告，进度只是观察通道，UI 消费
  失败最多丢进度，不该让提炼陪葬。代码注释与 `_emit` docstring 同述。
- 契约测试 6 例：正常路径全序列 / 多批总量一致 / 补问路径 / 失败路径（补问轮
  用尽不虚构 batch_done）/ 零批次 / 旁路。全套 424 绿 + mypy 干净（顺手清掉
  test_keil_patcher.py 存量 2 个类型错误）。
- 事件到 done/error 的接入 = 工单 02（webapp SSE 端点），本工单只管到 phase_done。
