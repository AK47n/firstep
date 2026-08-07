# 02 — 架构深化 v3：llm.py 批量 / 重试 / 打捞原语统一

**What to build:** 第三轮架构深化（improve-codebase-architecture 驱动，2026-08-06 报告候选 1：llm.py 是 12 次提交的热点，最近三次加固提交每次都在复制同一套"重试 → 严格解析 → 打捞 → 补问"循环）：

1. **重试补问循环统一为 `_retry_batch` 一个原语**：`_summarize_batch` / `_decide_batch` 是 ~45 行孪生（同形状：循环 SUMMARY_RETRY_LIMIT → _chat → 严格解析 → 打捞合法条目 → 只补问缺失路径 → 仍缺失大声失败），差异仅在 system prompt / user prompt 构造 / parse / salvage / 报错前缀——统一后重试政策单一 owner，坏条目不连坐的逐文件打捞语义（`_extract_good_summaries` / `_extract_good_decisions` / `_split_merged_versions`）保留为打捞策略。
2. **分批统一为 `_batches` 一个函数**：摘要阶段的预算分批（`_judgment_batches`：字符预算 24000 + 文件数上限 25 + 单文件多版本超预算按版本拆批）与判定阶段纯文件数分批（`_chunked`）收敛；`max_chars=None` = 无预算约束（判定阶段：摘要产物已小，注释说明的不对称保留）。删除单次使用的 `_chunked` 与 50 行的 `_judgment_batches`。

**约束：** 行为字节级不变——分批形状、调用序列、补问轮次、错误消息（`{phase_label}多次补问后仍缺失`，测试用 `match="多次补问后仍缺失"` 正则断言）全部保持；现有测试零断言改动。

**Status:** resolved

## Answer

- [x] `_retry_batch(system_prompt, user_prompt, parse, salvage, phase_label, items)` 唯一原语；I/R 双限定 TypeVar（摘要阶段：JudgmentFile→FileSummary；判定阶段：FileSummary→FileDecision——两阶段输入输出类型不同，单 TypeVar 表达不了）
- [x] `_summarize_batch` / `_decide_batch` 变薄包装（各 ~18 行纯参数绑定，保留阶段 docstring 与判例 08 说明）
- [x] `_batches(items, *, max_chars, size_of, split_oversized)`：`max_chars=MAX_SUMMARY_BATCH_CHARS` 时走预算 + 版本拆批（`_file_chars` / `_split_versions` 为阶段策略），`max_chars=None` 时纯文件数分批；删除 `_judgment_batches` / `_chunked`
- [x] 类型：限定 TypeVar（`TypeVar("I", JudgmentFile, FileSummary)`）而非 Protocol bound——mypy 2.3.0 在 `from __future__ import annotations` 下对 Protocol 属性约束的结构匹配实测不生效（最小复现验证过）；`max_chars` 给定但缺 size_of/split_oversized 时 raise ValueError（编程错误大声失败）
- [x] 测试：test_llm.py 4 个 `_judgment_batches` 直测改为本地 `_judgment_batches` 别名（镜像生产 `_summarize_judgment_files` 的调用参数），断言零改动
- [x] 全量 403 pytest 绿（重构前同量）+ mypy 17 个源文件干净
- [x] CONTEXT.md 不新增词条：统一的是实现机制而非领域概念，提炼行语义不变
