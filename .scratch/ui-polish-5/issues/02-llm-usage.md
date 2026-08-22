# 02 — LLM 用量与费用统计

**要做什么：** 5 处 `llm_telemetry` 回调统一接入 `recordLLMUsage`；会话内差分 + 跨会话累计持久化；设置页「LLM 用量统计」卡（本次会话 / 历史累计 / 估算费用 / 重置）。

**被谁阻塞：** 无。

**状态：** resolved

- [x] 纯函数：`usageDelta(snapshot, base)`（base=前次规范化返回值，字段缺失兜 0）/ `llmCostEstimate(usage, prices)`（缓存命中分档，空价兜底 0）/ `usageAccumulate(acc, delta)`（内联键名，不改原对象）/ `usageDisplay(acc, cost)`（¥ 四位小数 / —）
- [x] `recordLLMUsage(snapshot)`：基线差分（首快照全量→之后只计增量）+ 会话累计 + localStorage `firstep.usage.v1` 持久化 + renderUsageStats；5 处接入（rec L1751、fix `type==="llm_telemetry"` 分支、revise analyze/exec×2、prog L5123）
- [x] 设置页「LLM 用量统计」卡（应用设置与 AI API 之间）：本次会话/历史累计/重置按钮 + 提示行；tab 切设置时 renderUsageStats()
- [x] `tests/js/llm-usage.test.mjs` 8 用例（差分/费用分档/累加/显示）
- [x] CDP 验证：两次快照 → 会话=3 次（1 全量+2 差分，差分生效）、刷新后历史保留 3 次/会话归 0、重置清零；截图目检（位置/两列/无溢出）
- [x] 全量测试（js 84/84、契约 50/50）
