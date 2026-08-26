# 03 — 共享进度面板：static/js/ui/progress.js

**要做什么：** 推荐（recPanel，生成页）与提炼（distPanel，母版页）两个 SSE 工作流共用的**进度面板工厂** `makeProgressPanel`（含 nested tick / start / finish / handleEvent）迁入 `static/js/ui/progress.js`；纯函数 `fmtClock` / `fmtDuration` 迁入 `static/js/fx/core.js`（用户拍板：未测纯函数迁 fx + 补轻量单测）。两个**实例**（recPanel const / distPanel const + 各自事件回调）留在各自簇。

**被谁阻塞：** 02（app.js 提供 `$`）

**状态：** resolved（2026-08-27；JS 437 全绿（435+2 新增）、pytest 2465 全绿、diag 零 EXC、smoke 11/11、探针 03 通过）

## ⚠ 范围修正（实施时核实出的重大偏差）

- 工单正文原有「setStep / updateBatch / addLogLine / addBatchLine / startProgress / finishProgress / failProgress / MAX_LOG_LINES」列为共享件——**全部错误**：这些函数每一个都直接引用 `distPanel.p` / `distPanel.start()` / `$("prog-*")`（提炼容器）/ PHASE_LABEL / currentReport / renderReport，是**母版馆提炼专属胶水**，属 M 簇（工单 04）。recPanel 只经 makeProgressPanel 的 handleEvent/start/finish 工作，自己有一套 rec-* DOM。
- **真实共享面 = makeProgressPanel（工厂）+ fmtClock + fmtDuration（纯）三个名字**；原代码注释「===== 进度面板模块（工单 A 深化）：推荐 / 提炼两个 SSE 工作流共用的进度状态机 + 双计时器 + 事件分发 =====」严格描述的就是 makeProgressPanel 这一段（后续的 setStep 等在此注释之外）。distPanel 事件回调（start/batch_start/batch_done/retry/phase_done/llm_telemetry/done/error @7355-7401）与 PHASE_LABEL 7347 / MAX_LOG_LINES 7348 已全部确认留在 M 簇。
- fx 落点裁定：fmtClock/fmtDuration 就近入 **fx/core.js**（通用纯工具域，已有 esc/formatSize；spec 允许 fx/core.js 选项）；fmtSeconds 留在 E 簇按 spec 钉在 **工单 16** 迁 fx/generate.js（本票不碰）。
- 本票在 8902 行基线（工单 02 后）执行；8902 → 8853（净 -49）。

## 实施记录

- **static/js/fx/core.js**：fmtClock / fmtDuration 逐字搬移（含注释）+ window 桥 `{ esc, formatSize, fmtClock, fmtDuration }`。
- **static/js/ui/progress.js**（新建 ~43 行）：makeProgressPanel 逐字搬移；import `{ $ } from "/js/app.js"` + `{ fmtClock } from "/js/fx/core.js"`；头部注释 = 原 7407-7413 注释块改写（共享语义：{startedAt, lastEventAt, timerId, finished}、ADR 0004 每秒跳动证明、events.py 单点声明同步规则、两个实例属 A/M）。
- **tests/js/time-format.test.mjs**（新建，2 test / 8 断言）：fmtClock（00:00 / 59.9→"00:59" / 61→"01:01" / 3661→"61:01"）；fmtDuration（45→"45 秒" / 754→"12 分 34 秒" / 3723→"1 小时 2 分 3 秒" / 60→"1 分 0 秒"）。
- **tests/js/fx-guard.test.mjs**：core.js 块登记 fmtClock/fmtDuration（"fn"）——护栏 19 模块不变，仅改名数 19+2。
- **index.html（apply-03.mjs，CRLF 感知 + 边界钩子一次通过）**：①core.js import 行 `{ esc, formatSize }` → `{ esc, formatSize, fmtDuration }`（host 主体 finishProgress 仍引 fmtDuration）；②app.js import 行后插 `import { makeProgressPanel } from "/js/ui/progress.js";`；③删 7407-7458（注释块 7 行 + makeProgressPanel + 空行 + fmtClock + fmtDuration）→ 2 行注记；ⓘⓘ 删除前校验 removed span 含 3 名且**不含 setStep**（防越界吞 M 簇）；删除后校验：3 名零定义残留、makeProgressPanel({ 恰 2 处（recPanel 2675 / distPanel 7350）、M 簇符号全在（setStep/addLogLine/addBatchLine/updateBatch/startProgress/finishProgress/failProgress/MAX_LOG_LINES/PHASE_LABEL/currentReport/renderReport）。
- 验证：node --test 437 全绿（+2 新测）；pytest 2465 全绿（后台确认）；diag 零 EXC（favicon 404 既有噪音）；smoke 11/11；探针 probe-03-progress.mjs：动态 import makeProgressPanel ✓ window.fmtClock/fmtDuration 桥 ✓ host 无 function makeProgressPanel 定义 ✓ **实况飞行**（独立 #probe-recap DOM 实例化：start→1.15s 秒表跳动「总用时 00:01」/「当前轮已等待 00:01」、handleEvent("ping") 分发至回调、finish 后 finished=true 且 timerId=null）✓ rec/prog 面板 DOM 容器在位 ✓。

## 检查表

- [x] `static/js/fx/core.js`：fmtClock / fmtDuration + window 桥（已登记 fx-guard DOMAINS core.js 块）
- [x] `static/js/ui/progress.js`：makeProgressPanel 逐字搬移 + export + 头部注释（共享件、实例属 A/M、禁环同理不挂 window 桥）
- [x] `tests/js/time-format.test.mjs`：2 test / 8 断言（用户拍板：未测纯函数迁 fx 并补轻量单测）
- [x] index.html：apply-03.mjs（CRLF 感知；导入更新 + 删 7407-7458；边界钩子防越界）+ 零残留 + 调用点恰 2 处
- [x] node --test 437 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + 探针 03 实况飞行通过
- [x] 中文提交 + CHANGELOG 记录

## 风险点 / 跟踪

- 主体 import 行现为：`import { ..., fmtDuration } from "/js/fx/core.js"`（工单 04 迁出 finishProgress 后不再需要 fmtDuration，收尾时可从 core.js import 行裁掉——记录在工单 20）。
- distPanel 事件回调（7355-7401）引用的 PHASE_LABEL / MAX_LOG_LINES / setStep / add* 全部仍在主体，工单 04 整体迁 M 簇时一并处理。
