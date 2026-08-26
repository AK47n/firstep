# 10 — 设置 tab + LLM 用量 + 工作流胶水：static/js/ui/settings.js

**要做什么：** 设置 tab 全部 DOM 胶水迁入 `static/js/ui/settings.js`（配置加载 / 视觉预设同步 / 环境检查 / 价格参考 / 周期占位 / 单价收集 + 设置折叠 glue + LLM 用量统计 + 最近工作流渲染）。本票依赖工单 01（fx/workflow.js 的 wfNum / formatWorkflow* 供渲染）。**被谁阻塞：** 01（fx/workflow.js）+ 02（app.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 区段 A = 7927-8327：loadSettings 7927 / syncVisionProviderFromFields 8007 / applyVisionPreset 8018 / envCheckRun 8077 / renderPriceReference 8121（**pytest/tests/js 结构钉：price-reference-clear.test.mjs 钉函数体「清空语句在追加前 + tbody 存在」——tbody 是 markup 不动，函数体断言重指向 ui/settings.js**）/ periodPlaceholders 8148 / collectLlmPrices 8162（写 llmPricesDefaults 2336）；wfNum 8228 / formatWorkflowUsage 8232 / formatWorkflowCost 8240 / formatWorkflowSummary 8254 / formatWorkflowCall 8269（**工单 01 已迁 fx**）/ renderRecentWorkflows 8288 / loadRecentWorkflows 8312（读 wf 五件 + apiGet /api/recent/workflows）。
- 区段 B = 8876-9003：saveSettingsCollapse 8876 / initSettingsCollapse 8880（glue 8881-8944：toggle/master 按钮/写盘/刷新标签——调用 fx/settings.js 的 applySettingsCollapseState / effectiveCollapsed / settingsMasterLabel / settingsSectionHead 与 fx/generate.js 的 syncCollapseBtn）/ USAGE_STORE_KEY 8950 / usageBase 8952 / usageSessionAcc 8953 / loadUsageAcc 8954 / currentLlmPrices 8964 / recordLLMUsage 8975 / renderUsageStats 8984 / btn-usage-reset 监听 8997（top-level 随迁）。
- llmPricesDefaults（2336）：写方 collectLlmPrices → 调 llmCostEstimate（fx/llm.js）→ 随本簇拥有（从 app.js 共享区声明迁入 settings.js 或留 app.js？——裁定：本簇声明，读方 import）。
- markup：tab-settings @2024+；设置卡 data-collapse-id / 价格参考表 / 用量统计 id 全不动。
- host 页签分发器 import loadSettings + loadRecentWorkflows + renderUsageStats。

## 检查表

- [ ] 新建 `static/js/ui/settings.js`：上述区段 A/B 全部函数与常量逐字搬移 + import（app.js / fx/settings.js / fx/generate.js / fx/llm.js / fx/workflow.js）+ export（loadSettings / loadRecentWorkflows / renderUsageStats / renderPriceReference / initSettingsCollapse / saveSettingsCollapse / recordLLMUsage / currentLlmPrices / loadUsageAcc）+ 头部注释
- [ ] index.html：CRLF 感知行区间删除（A/B 两区；**物理升序**）+ 顶部 import 行追加
- [ ] tests/js/price-reference-clear.test.mjs：结构钉重指向 ui/settings.js（函数体断言）；若该钉在本票前已碎（renderPriceReference 随迁），本票修复
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 设置 tab 实况探针（探针先例 probe-10：折叠默认态 + 价格参考表渲染）
- [ ] grep 零残留：index.html 无 `function loadSettings(` 等定义
- [ ] 中文提交

## 风险点

- usageSessionAcc / usageBase 是**跨流程累计**（记录点 = 推荐/fix/revise SSE 的 llm_telemetry 事件 —— 跨簇调用 recordLLMUsage）：生成簇 import 本模块的 recordLLMUsage（单向）。
- collectLlmPrices 读设置页单价表（DOM 遍历）——若表单项 id 在 markup，逐字搬移无碍。
- 8895-8944 的 toggle 闭包（nested function）逐字搬移即可（nested 函数随宿主）。
