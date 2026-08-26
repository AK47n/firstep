# 03 — 共享进度面板：static/js/ui/progress.js

**要做什么：** 推荐（recPanel，生成页）与提炼（distPanel，母版页）两个 SSE 工作流共用的进度面板件迁入 `static/js/ui/progress.js`：makeProgressPanel（含 nested tick / start / finish / handleEvent）+ fmtClock + fmtDuration + setStep + updateBatch + addLogLine + addBatchLine + startProgress + finishProgress + failProgress + 共享常量（MAX_LOG_LINES）。两个面板**实例**（recPanel const 2735 / distPanel const 7415 + PHASE_LABEL 7413）留在各自簇，面板实例=「实例化配置 + 事件回调」即 glue。

**被谁阻塞：** 02（app.js 提供 `$` 与 toast）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- makeProgressPanel 7480（nested：tick 7485 / start 7490 / finish 7498 / handleEvent 7502）；fmtClock 7512；fmtDuration 7516；setStep 7526；updateBatch 7538；addLogLine 7553（用 MAX_LOG_LINES）；addBatchLine 7568；startProgress 7598；finishProgress 7620；failProgress 7631；MAX_LOG_LINES 7414。
- recPanel const 2735（推荐，events: round/converged/cache_hit/llm_telemetry/done/question/error —— 事件回调里调 renderRecommendResult/showRecommendQuestions/showRecommendError/recordLLMUsage/formatLLMTelemetry = 簇内/跨簇调用点，属 A 模块，**不随本票搬**）。
- distPanel const 7415 + PHASE_LABEL 7413 + 事件回调（start/batch_start/batch_done/retry/phase_done/done/error，7420-7470 用 setStep / addLogLine / addBatchLine / updateBatch）属 M 模块（工单 04），**不随本票搬**。
- fmtClock / fmtDuration 若被面板外的既有代码引用（如 renderReport 或 usage 展示），grep 确认后决定是否 export；引用方 import。
- 本票顺带裁定：fmtClock/fmtDuration 归 ui/progress.js（既非纯函数也非数据计算——若纯计算可迁 fx，实施时按「是否被测试/是否纯」裁定并记录）。

## 检查表

- [ ] 新建 `static/js/ui/progress.js`：上述件逐字搬移 + export（makeProgressPanel / fmtClock / fmtDuration / setStep / updateBatch / addLogLine / addBatchLine / startProgress / finishProgress / failProgress / MAX_LOG_LINES）+ 头部注释（共享件、两个面板实例属 A/M、源自工单 03）
- [ ] index.html:CRLF 感知行区间删除（7473-7479 区段注释 + 7480-7631 相关行；**物理升序**）+ 顶部 import 行追加
- [ ] 若面板件引用 `$`（prog-timer-total 等），import 自 app.js；若引用 fx 纯件（如 fmtClock 的格式化），import 自 fx
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11（推荐/提炼进度条冒烟触发点：生成页点推荐或母版页扫描后提炼）+ grep 零残留（10 名无 `function <名>(` 定义）
- [ ] 中文提交

## 风险点

- 删除区间与 distPanel（7415-7470）交错：本票只搬共享件，distPanel const + PHASE_LABEL + 事件回调**原地保留**，删除脚本必须按函数级精确 span，不得越界。
- makeProgressPanel 的 handleEvent 内若引用 `$` 之外的主体作用域符号，随迁时补齐 import。
