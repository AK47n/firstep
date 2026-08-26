# 17 — 生成页 · 修订工坊：static/js/ui/generate-revise.js

**要做什么：** generate tab 的「修订（revise）」簇迁入 `static/js/ui/generate-revise.js`（当前目录 / QA 计数 / 修订流水：load → context → analyze → apply → deepen → verify → rollback，SSE 分发 + diff 渲染 + 弃用/回滚）。**被谁阻塞：** 02（app.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数（5231-5702）：reviseCurrentDir 5231 / reviseCountQa 5236 / renderReviseTelemetry 5241 / clearReviseTelemetry 5246 / reviseSetBusy 5252 / reviseResetAll 5260 / reviseLoad 5286 / reviseRenderContext 5307 / reviseRunSSE 5336 / reviseRenderDiff 5365 / reviseRenderAnalysis 5380 / reviseDiscard 5420 / reviseAnalyze 5440 / reviseApply 5473 / reviseRenderApplyDone 5515 / reviseDeepen 5539 / reviseRunDeepen 5546 / reviseRenderVerify 5577 / reviseRenderDeepenDiff 5610 / reviseDiffLineHtml 5629 / reviseRollback 5637。
- 依赖：`$` / handle / apiGet / apiPost / apiDelete / state（app.js）；fx 域件（reviseDiffLineHtml 若纯 → 已测试?——grep tests/js 是否直测，无则保持胶水）；recordLLMUsage（ui/settings.js）；renderReviseTelemetry 用 formatLLMTelemetry（fx/llm.js）。
- markup：revise 区 id（revise-* 前缀，grep 确认）全不动；后端 /api/revise/* 不动。
- 修订流程用「两段式 API」（analyze 先返回待确认 → apply 确认后执行）——本簇 SSR 逻辑随迁。

## 检查表

- [ ] 新建 `static/js/ui/generate-revise.js`：上述 21 函数逐字搬移 + import（app.js / fx/llm.js / ui/settings.js / ui/progress.js（若用进度件））+ export（reviseLoad / reviseAnalyze / reviseApply / reviseRollback / reviseRunDeepen / reviseResetAll / reviseRenderContext）+ 头部注释
- [ ] index.html：CRLF 感知行区间删除（5231-5702 内目标名；**物理升序**）+ 顶部 import 行追加
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 修订区实况（reviseLoad 后 context 渲染）
- [ ] grep 零残留：index.html 无 `function reviseAnalyze(` 等 21 名定义
- [ ] 中文提交

## 风险点

- reviseRunSSE 是独立 SSE 运行器（不共用 progress.js 面板）——确认无共享件依赖后独迁。
- reviseDiffLineHtml / reviseRenderDiff 若含 diff 渲染纯计算且未测——按用户裁定「纯函数迁 fx + 补测」处理（实施时判断纯/胶水边界）。
