# Spec：亮色主题 + LLM 用量统计 + 细节打磨（ui-polish-5）

> 延续 ui-polish 系列迭代。用户从 12 项候选中选定：7 亮色主题切换、4 LLM 用量与费用统计、11 细节打磨包。

## 问题陈述

1. 全站只有深色主题，长时间使用偏累；CSS 变量已集中在 `:root`，切换成本可控；
2. 用户关心 LLM 成本（设置页已配单价/计费时段），但没有任何用量与费用统计；
3. 滚动条为系统默认、按钮 loading 态样式分散、禁用态视觉不统一。

## 方案

### 01. 亮色主题切换

- `html[data-theme="light"]` 覆盖全部 `:root` 颜色变量（GitHub 亮色系：浅底 #f6f8fa、白面板、深青强调），`color-scheme: light`；
- 顶栏最右加主题切换按钮（🌙/☀️ 随当前主题显示），点击切换；偏好存 localStorage `firstep.theme`，脚本加载时尽早应用（防闪烁）；
- 引脚板图 SVG 两处硬编码 `fill="#0d1117"` 改为 `fill="var(--bg)"`；
- 硬编码青色微光/渐变（按钮、step-no、胶囊、进度条等）保持青色不变，亮底下自动成立。

### 02. LLM 用量与费用统计

- 数据源：现有 `llm_telemetry` SSE 快照（累计值：`llm_total_calls` / `llm_usage.{prompt_tokens,completion_tokens,total_tokens}` / `llm_duration_ms` / `llm_request_bytes`），5 处回调统一挂 `recordLLMUsage(snapshot)`；
- 会话内差分：首快照建基线，之后 `delta = snapshot - base`，避免重复累计；delta 实时并入跨会话累计并持久化 localStorage `firstep.usage.v1`（刷新不丢）；
- 费用估算：按当前计费时段（peak/off_peak）取单价（输入框值优先，空则 `llmPricesDefaults` 官方价）；输入分缓存命中/未命中两档（usage 有 `prompt_cache_hit_tokens` 则按档拆分，否则全按未命中）；
- 展示：设置页新增「LLM 用量统计」卡——本次会话（调用次数 / prompt / completion / 耗时）/ 历史累计（同上 + 估算费用）/「重置统计」按钮；
- 纯函数：`usageDelta(snapshot, base)`、`llmCostEstimate(usage, prices)`、`usageAccumulate(acc, delta)`、`usageDisplay(acc)` 可被 tests/js 抽取。

### 03. 细节打磨包

- WebKit 滚动条美化（细条、圆角、变量驱动，亮暗自适应）；
- `.spinner` 统一（尺寸/边框/动画已有，补 `prefers-reduced-motion` 降级）；
- `textarea/input:disabled` 视觉；按钮禁用态统一（保留现有 opacity + cursor，加 transition）；
- 主按钮含 spinner 时 flex 对齐（按钮行内 spinner+文字垂直居中）。

## 实现决策

- 只改 `src/contest_generator/static/index.html` + 新增 `tests/js/*.test.mjs`；后端零改动、API 契约零改动。
- 主题切换按钮放 header 内 nav 之后（`margin-left` 自动布局）。
- 用量统计接入 5 处 llm_telemetry 回调（rec / fix / revise analyze+exec / prog），统一调 `recordLLMUsage`。
- 视觉回归：无头 Edge + CDP 截图（亮色全页 / 暗色切换 / 统计卡 / 滚动条）+ 计算样式断言（data-theme 切换后 body 背景色变化）。

## 测试决策

- 新增 `tests/js/llm-usage.test.mjs`（usageDelta 首快照/重复快照/字段缺失、llmCostEstimate 缓存分档/空价兜底、usageAccumulate 累加与越界）；
- `node tests/js/*.test.mjs` + `pytest tests/test_generate_check_contract.py` 全绿；全量 pytest 后台跑一次保底。

## 范围外

- 不做自动跟随系统主题（用户手动切换）；不改后端单价存储结构；不做主题化重绘 SVG 板图全貌。
