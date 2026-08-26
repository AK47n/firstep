# 09 — LLM 用量与遥测域：fx/llm.js（≈10 函数）

**要做什么：** LLM 用量统计 / 成本估算 / 遥测格式化 / SSE 解析 / 推荐进度全部被测试纯函数迁入 `static/js/fx/llm.js`；llm-usage / llm-telemetry-format / sse-parser / recommend-telemetry 测试改为 import；页面零变化。

**被谁阻塞：** 01（core.js）

**状态：** ready-for-agent

- [ ] 新建 fx/llm.js：usageDelta / usageAccumulate / llmCostEstimate / usageDisplay / formatLLMTelemetry / parseSSE / startProgress / startRecProgress 及域内常量；尾部 window 桥
- [ ] index.html 删除上述定义；加载 `<script type="module" src="/js/fx/llm.js">`
- [ ] 四个测试文件改 import（注意 sse-parser 用浏览器同构 Response/ReadableStream 测试——parseSSE 迁出后测试改为 import 直测，用例不动）
- [ ] `node --test` 全绿；冒烟生成页 telemetry 区
