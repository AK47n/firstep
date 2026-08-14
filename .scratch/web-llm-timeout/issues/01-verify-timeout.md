# 01 — web 端 LLM 读超时 300s 验证与同步（check-recommend-cache/01 follow-up）

**What to build:** 验证 web 端 `/api/recommend` 单次 LLM 调用是否可能触达
`DeepSeekLLM.TIMEOUT_SECONDS = 300`（src/contest_generator/llm.py:659）并造成
TimeoutError 误杀；若确认，提高超时（或提为 config 键）并核对 `_retry_parse`
网络类重试在"调用其实在算"场景的语义。

**Status:** resolved

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

- [x] 真机观察记录（web 单调用时长 vs 300s）写进 Comments
- [x] 若需修改：pytest 全绿 + mypy src 干净 + 真机 /api/recommend 跑通（不适用——决策 1 走证据闭环未改 src；真机跑通已由本次观察完成，pytest/mypy 零改动后复跑确认分支绿）
- [x] 若无需修改：证据闭环记录，Status resolved 并说明

## Comments

### 2026-08-14 证据闭环（决策 1：未触达 300s，零代码改动）

**读码核实（验证前先搞清超时作用路径）**

1. **LLM 层无流式调用**：`_chat`（llm.py:1291）请求体只有 model/messages/response_format，全 src grep 无 `stream: True`（webapp 的 StreamingResponse 是服务端→浏览器 SSE，与 LLM HTTP 调用无关）。TIMEOUT_SECONDS=300 经 llm.py:1312 → UrllibTransport.post llm.py:631 `urlopen(timeout=300)`，约束**非流式整读**。socket 超时是每操作级（连接 + 每 recv），非流式下 DeepSeek 生成完成前不发任何字节 → 实际约束 = **首字节时延（生成时长）< 300s**，首字节到达后 body 连片到达。"流式逐块读超时语义"问题不成立——不存在流式 LLM 调用。
2. **CLI 600s 为何先于服务端 300s 被杀**：两者范围不同。CLI 600s = 客户端读 SSE 事件流的静默窗口（**轮级**）；轮 1 是两次背靠背 select_modules（清单级 + 点名全文回读，selection.py:776/786），轮间才发 EVENT_ROUND——静默窗口 = 两连调用之和，可 >600s 而每调用 <300s。服务端 300s = **单调用级**。2026-08-14 首跑 CLI 被杀是轮级累计超限，不是单调用触达 300s（若单调用触达，服务端先杀 → 网络类退避重试或抛 error 事件，CLI 600s 内会收到 error 而非纯静默）。
3. **超时与 _retry_parse 交互（已核对，不改）**：urlopen 内 socket 超时 → TimeoutError（OSError 子类）→ UrllibTransport `except (URLError, OSError)` → kind=network → ≤NETWORK_RETRY_LIMIT=5 次指数退避 1/2/4/8s（llm.py:883-902）。慢调用（其实在算）超时**会**被当网络错误重试，且每次重发全量请求（token 再计费）——若生成稳定 >300s，5 次全灭 ≈25 分钟 + 5× 费用后大声失败。语义已核对：此为 deepseek-retry-hardening/01 既定设计（网络瞬断重试价值成立），实测未触达故不改动；若未来上下文显著增大（单调用逼近 300s），本工单观察方法可直接复测。

**真机观察（2026-08-14 08:37-08:42，8000，web-llm-timeout worktree，真实 DeepSeek）**

请求 = 2026C stm32 + 全量澄清 8 条（与 check_2026C_cache_write 同源形状），请求体 12505 字节；观察脚本客户端读超时放宽 3600s（观察对象是服务端单调用，客户端不能先杀）。SSE 逐事件时间戳（elapsed 自请求发出）：

| 事件 | elapsed | 间隔 = 调用时长 |
|---|---|---|
| round 1 发出 | 1.9s | — |
| round 2 发出 | 135.8s | 轮 1 合计 133.9s（两连调用：清单级+全文回读；单调用 ≤134s） |
| round 3 发出 | 216.3s | 轮 2 单调用 80.5s |
| round 4 发出 | 266.0s | 轮 3 单调用 49.7s |
| converged + done | 306.0s | 轮 4 单调用 40.0s |

全程无 error/question 事件，4 轮收敛 done（载荷 1936 字）。**单调用峰值 ≤134s，距 300s 有 2.2× 余量**；轮间隔 <300s 在数学上排除"隐藏 300s 超时 + 重试成功"的可能（一次超时本身就要 300s）。web 端不会同病误杀——与 CLI 修前不同，web 300s 约束的是单调用首字节时延，而单调用实测远未触达。

**结论：无需修改。** TIMEOUT_SECONDS=300 保持（判例 08 注释的量级仍成立）；_retry_parse 网络重试语义保持。零 src 改动。顺带旁证：check_2026C_cache_write 真机（3 轮 ≈510s 推荐段）同样与"每调用 <300s"自洽。

**证据文件**：`.scratch/real-run/web_timeout_observe.py`（观察脚本，非 src）+ `web_timeout_observe_2026C.log`（逐事件时间戳全量）。
