# 01 — web 端 LLM 读超时 300s 验证与同步（check-recommend-cache/01 follow-up）

**What to build:** 验证 web 端 `/api/recommend` 单次 LLM 调用是否可能触达
`DeepSeekLLM.TIMEOUT_SECONDS = 300`（src/contest_generator/llm.py:659）并造成
TimeoutError 误杀；若确认，提高超时（或提为 config 键）并核对 `_retry_parse`
网络类重试在"调用其实在算"场景的语义。

**Status:** open

**Blocked by:** 无。

## 现状证据（2026-08-14，check-recommend-cache/01 grilling 裁决 ②）

- CLI 真机实测：提速棱镜 A"一轮问全"后，单轮 LLM 静默窗口超 600s（2026C
  首跑被 CLI 读超时 600s 误杀，整次推荐白跑）。CLI 侧已修：recommend_stream
  / fix_stream 读超时 600→1800s（.scratch/real-run/generate_check.py:218/:371）。
- web 端每次 LLM 调用读超时 = `DeepSeekLLM.TIMEOUT_SECONDS = 300`
  （llm.py:659，经 llm.py:1312 → UrllibTransport.post → llm.py:631 urlopen
  timeout）。与 CLI 修前 600s 同理，单调用静默超 300s 即 TimeoutError；
  `_retry_parse` 网络类会指数退避重试 ≤5 次（llm.py，ERROR_KIND_NETWORK，
  工单 deepseek-retry-hardening/01）——超时重试对分钟级慢调用是否恰当
  （重跑 10 分钟级的调用 = 白烧）需一并核对。
- 未实测 web 单调用是否真超 300s（"一轮问全"后真机推荐主要在 CLI 跑，
  web 层单调用时长无直接观察记录）。

## 决策记录（代决，用户可 grilling）

1. **先验证后修改**：真机 /api/recommend 观察单次 select_modules 调用时长
   （uvicorn 日志时间戳足够），未触 300s 即证据闭环不修改。
2. 若确认：TIMEOUT_SECONDS 提高（参考 CLI 1800s 量级，或提为 config 键）；
   核对 _retry_parse 网络重试语义。
3. 边界：不动 CLI 侧（1800s 已闭环）；不动 recommend 协议。

## 验收标准

- [ ] 真机观察记录（web 单调用时长 vs 300s）写进 Comments
- [ ] 若需修改：pytest 全绿 + mypy src 干净 + 真机 /api/recommend 跑通
- [ ] 若无需修改：证据闭环记录，Status resolved 并说明
