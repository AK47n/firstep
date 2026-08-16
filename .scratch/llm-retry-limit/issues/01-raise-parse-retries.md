# 01 — 解析类模型请求重试上限 3 → 5

**What to build:** 用户反馈：模型请求两次失败就停、需要手动说继续。把解析类（空内容 / 畸形 JSON / 业务失败）快重试上限 `SUMMARY_RETRY_LIMIT` 从 3 提高到 5，与网络类 `NETWORK_RETRY_LIMIT` 对齐；同步更新注释与钉死旧值 3 的测试。

**Blocked by:** 无

**Status:** resolved（2026-08-15）

## Comments

- 行为变化：解析类（空内容/畸形 JSON/业务失败）从「3 次总尝试（首试 + 2 次重试）」改为「5 次总尝试（首试 + 4 次重试）」，仍无退避 sleep；网络类仍 5 次指数退避（1/2/4/8s），两类现在对称。
- 批处理补问轮（蒸馏摘要/判定）同样吃 SUMMARY_RETRY_LIMIT，同步从 3 轮变 5 轮；成功路径不受影响（成功后立即停止，不会多花钱）。
- 测试全部用常量引用，以后调上限只改 llm.py 一处。

- [x] `llm.py` SUMMARY_RETRY_LIMIT = 5（快重试，无退避 sleep）
- [x] `_retry_parse` / `_retry_batch` 相关注释与硬编码“≤3 / 3 次”文案更新
- [x] tests/test_llm.py 旧值 3 的用例改为 5 / 用常量（成功路径 2 次空内容 + 1 次成功不受影响）
- [x] pytest 全绿 + mypy src 干净
