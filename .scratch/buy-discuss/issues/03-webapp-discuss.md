# 工单 03：webapp 端点 POST /api/buy/discuss（一轮讨论）

> 来源：.scratch/buy-discuss/spec.md §2.1（§四 实现决策 1/5/7）
> 状态：resolved（双轴评审通过 + 整改：Standards 5 项 / Spec 3 项，E2E 10/10）

**要做什么：**
- `webapp.py`：POST `/api/buy/discuss`（同步 JSON，非 SSE）——请求 {problem_text, requirement, platform, solutions（词表行级或全部？取调用侧读词表 + 前端传建议名，服务端按名取 solutions）, history: [{role, content}]}；装配域上下文 → `llm.discuss_buy_options` → 响应 {reply, review}。
- 读词表：服务端 load_wordlist 后按建议名（或类别）匹配行填 solutions（词表外 = 空 solutions，仅题面+需求+历史讨论——不编造方案文本）。
- 校验：缺 problem_text / history 非数组 / role 非法 → 400 中文；LLMError → 422/400（照既有 deep 端点翻译）。
- telemetry：llm_telemetry 采集（create_llm_observation_collector + bind_llm_telemetry 先例）。

**被谁阻塞：** 01（协议）、02（无强依赖，可并行）。

**验收标准：**
- [x] 端点正常流：一轮讨论返回 {reply, review}（review 可空）
- [x] payload 校验 400（缺题面 / history 非法 / role 词表外）
- [x] LLM 失败错误翻译 + telemetry 采集
- [x] tests/test_webapp.py 绿；中文 commit（工单 03）
