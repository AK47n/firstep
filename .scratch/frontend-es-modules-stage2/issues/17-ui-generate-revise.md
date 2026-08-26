# 17 — 生成页 · 修订工坊：static/js/ui/generate-revise.js

**要做什么：** generate tab 的「修订（revise）」簇迁入 `static/js/ui/generate-revise.js`（当前目录 / QA 计数 / 修订流水：load → context → analyze → apply → deepen → verify → rollback，SSE 分发 + diff 渲染 + 弃用/回滚）。**被谁阻塞：** 02（app.js）

**状态：** 已实施（resolved）

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数（5231-5702）：reviseCurrentDir 5231 / reviseCountQa 5236 / renderReviseTelemetry 5241 / clearReviseTelemetry 5246 / reviseSetBusy 5252 / reviseResetAll 5260 / reviseLoad 5286 / reviseRenderContext 5307 / reviseRunSSE 5336 / reviseRenderDiff 5365 / reviseRenderAnalysis 5380 / reviseDiscard 5420 / reviseAnalyze 5440 / reviseApply 5473 / reviseRenderApplyDone 5515 / reviseDeepen 5539 / reviseRunDeepen 5546 / reviseRenderVerify 5577 / reviseRenderDeepenDiff 5610 / reviseDiffLineHtml 5629 / reviseRollback 5637。
- 依赖：`$` / handle / apiGet / apiPost / apiDelete / state（app.js）；fx 域件（reviseDiffLineHtml 若纯 → 已测试?——grep tests/js 是否直测，无则保持胶水）；recordLLMUsage（ui/settings.js）；renderReviseTelemetry 用 formatLLMTelemetry（fx/llm.js）。
- markup：revise 区 id（revise-* 前缀，grep 确认）全不动；后端 /api/revise/* 不动。
- 修订流程用「两段式 API」（analyze 先返回待确认 → apply 确认后执行）——本簇 SSR 逻辑随迁。

## 检查表

- [x] 新建 `static/js/ui/generate-revise.js`：上述 21 函数逐字搬移 + import（app.js / fx/llm.js / ui/settings.js / ui/progress.js（若用进度件））+ export（reviseLoad / reviseAnalyze / reviseApply / reviseRollback / reviseRunDeepen / reviseResetAll / reviseRenderContext）+ 头部注释
- [x] index.html：CRLF 感知行区间删除（5231-5702 内目标名；**物理升序**）+ 顶部 import 行追加
- [x] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 修订区实况（reviseLoad 后 context 渲染）
- [x] grep 零残留：index.html 无 `function reviseAnalyze(` 等 21 名定义
- [x] 中文提交

## 实施记录（工单 17）

### 行号复核
簇体实际位于 2489-2964（修订与深化 section 注释 → 模块库页 section 注释，不含后者）：let revise 2496 / reviseCurrentDir 2508 / reviseCountQa 2513 / renderReviseTelemetry 2518 / clearReviseTelemetry 2523 / reviseSetBusy 2529 / reviseResetAll 2537 / reviseLoad 2563 / reviseRenderContext 2584 / reviseRunSSE 2613 / reviseRenderDiff 2642 / reviseRenderAnalysis 2657 / reviseDiscard 2697 / reviseAnalyze 2717 / reviseApply 2750 / reviseRenderApplyDone 2792 / reviseDeepen 2816 / reviseRunDeepen 2823 / reviseRenderVerify 2854 / reviseRenderDeepenDiff 2887 / reviseDiffLineHtml 2906 / reviseRollback 2914 + 8 监听器（2941-2964：btn-revise-session / btn-revise-load-dir / revise-dir-input Enter / btn-revise-analyze / btn-revise-discard / btn-revise-apply / btn-revise-deepen / btn-revise-rollback / revise-problem-text input）。issue 正文行号（5231-5702）为阶段 1 时代编号。

### 搬迁边界与裁定
- **ui/generate-revise.js（509 行 LF）**：revise 状态对象 + 21 函数 + 8 监听器顶层绑定（import 时绑）。
- **依赖极简**：app.js（$ / apiPost / toast）+ fx/core.js（esc）+ fx/llm.js（parseSSE / formatLLMTelemetry）+ ui/usage.js（recordLLMUsage，非 issue 所说 ui/settings.js）+ ui/step-state.js（markStepDone）。**无跨簇状态读**（A/fix/pins 零交叉；reviseRunSSE 独立运行器——确无 progress.js 共享件）；revise.p.* render context 渲染（2568-2582）经 reviseRenderContext。
- **reviseDiffLineHtml / reviseCountQa / reviseRenderDiff 纯计算但 tests/js 零直测** → 按 issue 裁定保持胶水随簇迁（后续如需直测按「纯函数迁 fx + fx-guard 登记」先例）。
- **导出面（7 名）**：照检查表；host 实际零调用点。
- **⚠ 关键决策：host 零调用点也必须加 import 行** —— 顶层监听器绑定依赖模块加载；不带 import 行则模块根本不加载（实况探针抓到：监听器全部失效、守卫文案不触发——probe-17 首跑 FAIL）。host import 行（2248）附注释「host 零调用点——import 只为加载模块」。这是「import 即加载器」的先例，记入后续工单（readiness/steps 若零调用点同样处理）。

### 验证矩阵（全绿）
- node --test：444/444；pytest：2465 passed（既有噪声）；diag 零 EXC；smoke 11/11。
- probe-17.mjs：7/7（动态 import 导出齐全 / btn-revise-session 守卫「请先生成工程」/ btn-revise-analyze 守卫「请先加载上下文」/ revise-problem-text input 即时更新 / revise-dir-input Enter → reviseLoad 后端 400 文案「输出目录不存在」/ 全程零 EXC）。
- grep 零残留：22 名（21 函数 + let revise）在 index.html 无定义；markup id（btn-revise-* / revise-*）未动。

### 探针教训（追加）
- ①hidden 容器内按钮 getBoundingClientRect = 0（分析卡 revise-analyze-box 默认 hidden，加载上下文后才可见）——CDP 坐标点击落空；守卫性/防御性路径用 DOM click 直测监听器。②「host 零调用点 ≠ 不需要 import 行」——模块加载必须有一处 import。

## 风险点

- reviseRunSSE 是独立 SSE 运行器（不共用 progress.js 面板）——确认无共享件依赖后独迁。
- reviseDiffLineHtml / reviseRenderDiff 若含 diff 渲染纯计算且未测——按用户裁定「纯函数迁 fx + 补测」处理（实施时判断纯/胶水边界）。
