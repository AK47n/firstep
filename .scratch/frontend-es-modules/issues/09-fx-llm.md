# 09 — LLM 用量与遥测域：fx/llm.js（6 函数）

**要做什么：** LLM 用量统计 / 成本估算 / 遥测格式化 / SSE 解析 / 推荐进度全部被测试纯函数迁入 `static/js/fx/llm.js`；llm-usage / llm-telemetry-format / sse-parser / recommend-telemetry 测试改为 import；页面零变化。

**被谁阻塞：** 01（core.js）

**状态：** resolved（2026-08-26；JS 416 全绿 + 浏览器冒烟 11/11）

## 实施记录

- 数字修正：工单标题「≈10」，实际迁移 = 6 个纯函数：usageDelta / usageAccumulate / llmCostEstimate / usageDisplay / formatLLMTelemetry / parseSSE；域内常量无（USAGE_STORE_KEY 由胶水层 loadUsageAcc/clear 使用，留内联）。
- **startProgress / startRecProgress 明确不迁**（工单清单偏离，同 08 的 renderPriceReference 先例）：二者是 DOM 胶水（recPanel.start / distPanel.start / $() / classList），迁入模块会 ReferenceError（recPanel / distPanel / $ 均在主体脚本作用域）；recommend-telemetry.test.mjs 是源码结构钉（断言 recPanel 定义与 handler 接线），全部保持内联 + 测试原样。
- fx/llm.js：函数体逐字搬移 + docstring 全保留（formatLLMTelemetry 的中文标签表 / parseSSE 契约注释 / usage 头部注释）；无共享件依赖；尾部 window 桥 6 名。
- index.html：主体 module 顶部 import 行追加（readiness.js 之后）；3 处 CRLF 感知行区间删除（L1 48 行 formatLLMTelemetry / L2 41 行 parseSSE（含「SSE 解析器结束」标记行——end 锚点按「} + 结束标记」特判）/ L3 49 行 usage 四函数），内容锚定 + span 校验通过；胶水留内联：renderFixLLMTelemetry / clearFixLLMTelemetry / makeProgressPanel / recPanel / distPanel / startRecProgress / stopRecProgress / startProgress / loadUsageAcc / currentLlmPrices / recordLLMUsage / renderUsageStats / usageBase / usageSessionAcc。
- 测试改造（3 文件整头换 import）：llm-usage（usageDelta / usageAccumulate / llmCostEstimate / usageDisplay）、sse-parser（parseSSE——浏览器同构 Response/ReadableStream 用例原样，仅导入方式变化）、llm-telemetry-format（formatLLMTelemetry）；fs/html/extract 全删（html 仅抽取用）。recommend-telemetry.test.mjs 不变。
- 验证：`node --test "tests/js/*.test.mjs"` 416 全绿；diag.mjs 零 EXC（favicon 404 既有噪音）；smoke.mjs 11/11；grep 零残留（6 名无 `function <name>(` 定义）。

- [x] 新建 fx/llm.js：usageDelta / usageAccumulate / llmCostEstimate / usageDisplay / formatLLMTelemetry / parseSSE 及域内常量；尾部 window 桥（startProgress / startRecProgress 不迁——DOM 胶水，见记录）
- [x] index.html 删除上述定义；加载 `<script type="module" src="/js/fx/llm.js">`
- [x] 四个测试文件改 import（注意 sse-parser 用浏览器同构 Response/ReadableStream 测试——parseSSE 迁出后测试改为 import 直测，用例不动；recommend-telemetry 为结构钉，保持不变）
- [x] `node --test` 全绿；冒烟生成页 telemetry 区
