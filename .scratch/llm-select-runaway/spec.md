# Spec：模块推荐 LLM 输出失控修复（deepseek-v4-flash 20K tokens 输出 + 解析失败）

## 问题（用户报告 + telemetry 实证）

「检查一下ai推荐模块，现在第一轮已经跑好久了」。telemetry 实况：

- LLM 2 次调用 · 本地 0 / DeepSeek 2 · 最新 选模块 · 错误 parse/解析 解析失败 · HTTP 200
- 尝试 2, 重试 1, 错误 2, 解析错误 2 · 请求 69,646B · 耗时 322,824ms
- 用量 prompt=10630, completion=41150（≈20575/次——select 正常输出应几百 token，异常巨大）

服务进程（uvicorn 127.0.0.1:8000，python -m contest_generator.webapp）在 10:02 启动，出站 Established 连接指向 api.deepseek.com（43.242.198.77:443）持续活跃——推荐仍在第 3+ 次尝试中。

配置（C:\Users\luoji\.contest_generator\config.json）：model=deepseek-v4-flash（远程），recommend_max_rounds=4。

## 根因分析

- llm.py:2063 `_chat_once` payload 只有 `{"model", "messages"}`（+json_mode 时 response_format）——**无 max_tokens 字段**，输出长度完全交给服务端默认。deepseek-v4-flash 默认上限 ≥ 20K，模型输出 20K tokens 的畸形/超长 JSON（疑似输出退化：把逐句分析/自检过程写进 JSON）。
- 解析失败链：输出超长或畸形 → extract_module_selection_data / build_module_selection 失败 → LLMError(parse) → `_retry_parse` 重试（SUMMARY_RETRY_LIMIT=5）——**每次重试重复生成 ~20K tokens、耗时 ~160s**，用户体验为「第一轮跑好久」，且每次重试都在重复烧钱。
- 观测结构（LLMCallObservation）不含响应内容——无法事后确认失败响应长什么样（脱敏契约，本次加脱敏摘要）。

## 方案（最小修复集）

1. **max_tokens 上限**：`_chat_once` 与 `_retry_parse` 加 `max_tokens: int | None = None` 透传参数（None = 不加字段，其他调用零影响）；`select_modules` 传 `SELECT_MAX_OUTPUT_TOKENS = 4096`（select 合理输出 < 2K tokens，4096 足够；超长被服务端截断 → JSON 不完整 → 快速 parse 失败，单次生成时间从 ~160s 降到 ~30-60s）。
2. **超长守卫（免重试）**：select parse 闭包检查 `len(content) > 60000`（≈15K tokens，远超合理输出）→ `raise LLMError(..., kind=ERROR_KIND_CLIENT)`——`_retry_parse` 对 client 错误已 break 不重试（llm.py:1375-1378 既有分支），输出退化时不重复烧钱。
3. **响应留痕（脱敏摘要）**：`LLMCallObservation` 加 `content_excerpt: str | None`（响应内容前 120 字符、换行压平、超长加省略号；不破坏「不含 prompt/response/key」脱敏契约——只留前缀诊断信号）；`collect`/`_observe_call`/`_observe_chat_result`/`to_log_extra` 透传。下次异常可直接从 telemetry/日志看响应头。
4. **提示词加固（治标）**：SELECT_SYSTEM_PROMPT 末尾加一句「输出保持紧凑：每条需求描述 ≤ 40 字、reason ≤ 20 字、不重复题面原文」。

## 范围外

- 不改其他 LLM 调用（deepen/fix_compile_errors 等需要长输出的保持无上限）。
- 不改重试次数 / 收敛循环 / 前端 telemetry 展示（content_excerpt 随观测 dict 序列化自动出现，前端若未渲染不做前端改动）。
- 不换模型、不改用户配置（换模型是用户侧决策，可在总结中建议）。

## 验收

- select_modules 请求 payload 含 `max_tokens=4096`（FakeTransport 捕获断言）；其他调用 payload 无 max_tokens 字段（现状不变）。
- 超长输出（>60000 字符）→ LLMError kind=client，仅 1 次尝试（transport.calls 长度断言）。
- 失败响应观测含 content_excerpt（collector 断言）；to_log_extra 带出。
- 全量测试绿 + mypy 干净；重启服务生效。
