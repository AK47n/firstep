# 03 — 重试分类与累计预算

**What to build:** LLM 调用和复杂工作流按错误类别采用可解释的重试策略，并在达到累计尝试/耗时预算时明确终止，避免不可恢复错误和模型异常无限放大成本。

**Blocked by:** 02 — LLM 调用结构化观测

**Status:** resolved

- [x] 400/401/403/404 等不可恢复错误默认不重试
- [x] 429 使用服务端 `Retry-After`（无值时采用安全退避）
- [x] 网络错误与 5xx 使用有限指数退避
- [x] 空内容、JSON 解析错误、领域校验错误使用独立且有限的重试策略
- [x] 工作流支持可选累计尝试次数和累计耗时预算
- [x] 预算耗尽返回明确中文业务错误且不产生残缺副作用
- [x] 缺省预算保持既有成功路径兼容
- [x] 相关重试、预算和错误映射测试通过
- [x] 运行全量 pytest、mypy 和 Node 测试

## Notes

- `RetryBudget` 支持累计尝试次数与累计耗时；`build_llm` 可注入共享预算，RoutingLLM 的 remote/local 委托共用同一预算。
- `_retry_parse`、`_retry_batch` 与兼容 `_chat` 入口统一 HTTP/网络/429/解析类重试分类，重试耗尽保留最后一次 `LLMError.kind`。
- 推荐、骨架、提炼、归档确认、编译修复等多调用工作流接入共享预算；预算耗尽发生在写盘/`apply_fixes` 前。
- 验证：`python -m pytest -q`、`python -m mypy src`、`node --test`；code-review 双轴复审无剩余 blocker。
