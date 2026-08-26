# 04 — 母版页 + 更新记录试点：static/js/ui/master.js（含 distPanel / 报告 / 扫描）+ loadChangelog

**要做什么：** 母版 tab 全部 DOM 胶水迁入 `static/js/ui/master.js`（含 distPanel 实例与提炼事件回调、扫描/暂存目录、报告渲染与确认、母版库表格、文件查看、删除确认、loadChangelog 更新记录——changelog 为独立小 tab，随母版合入同一文件）。本票是 ui 模块化第一张完整 tab 切片，验证「02 app.js 共享壳 + 03 progress.js 共享件 + 04 域模块」三层结构成立。**另拆 ui/usage.js：LLM 用量记录服务（跨簇共享，见「前置拆分」）。**

**被谁阻塞：** 02（app.js）+ 03（progress.js）

**状态：** resolved（2026-08-27；JS 440 全绿（437+3 新增）、pytest 2465 全绿、diag 零 EXC、smoke 11/11、探针 04 通过）

## ⚠ 前置拆分：ui/usage.js（依赖事实驱动，新增）

- 母版 distPanel 的 llm_telemetry 回调调 **recordLLMUsage**（原 7399），而该名在用量簇（仍 host）——模块无法 import host 作用域。且 recordLLMUsage 同时被推荐（2705）/ 修复（4848）/ 修订（5400/5433/5502）三流引用 = 跨 4 簇共享服务。
- 裁定：**新建 ui/usage.js 提前拆出「用量记录服务」**——USAGE_STORE_KEY / usageBase / usageSessionAcc / llmPricesDefaults（所有权 + `setLlmPricesDefaults` 写入 + `export let` 活绑定只读）/ loadUsageAcc / currentLlmPrices / recordLLMUsage / renderUsageStats / btn-usage-reset 监听。纯计算在 fx/llm.js；app.js 只被 import（单向无环）。
- host 侧 3 处适配：①`let llmPricesDefaults = {};`（原 2276）删除→注记；②loadSettings 写入点（原 7854）`llmPricesDefaults = s.llm_prices || {};` → `setLlmPricesDefaults(...)`；③collectLlmPrices 的两处读（原 8054/8064）无需改——ESM 活绑定只读合法；host import 增 `{ recordLLMUsage, llmPricesDefaults, setLlmPricesDefaults, renderUsageStats }`（分发器 @2267 调 renderUsageStats）。
- spec 工单 10 的 usage 清单随之收缩（只剩 loadUsageAcc 渲染面已迁净——工单 10 不再含用量域）。

## 实施记录

- **static/js/ui/master.js**（新建 ~490 行）：整区逐字搬移（状态 scannedProjects/currentReport/stagedDirs/masterCache/masterFileCache + projectDirs/renderStagedDirs + 6 个顶层监听（btn-pick-dirs/pick-dirs/btn-scan/prog-log-head/btn-distill/btn-confirm）+ PHASE_LABEL/MAX_LOG_LINES/distPanel 实例 + setStep/updateBatch/addLogLine/addBatchLine/startProgress/finishProgress/failProgress + renderReport + openMasterDeleteConfirm/loadMasterFileState/renderMasterFileContent/openMasterFile/openMasterDetail/loadMasters/loadChangelog）；**decisionItem/archiveItem 不在本模块**——纯 HTML 构建器迁 fx/master.js（用户拍板③+补测）；export 仅 loadMasters/loadChangelog（host 分发器需求面）。import：app.js（$/handle/apiGet/apiPost/apiDelete/toast）+ ui/progress.js（makeProgressPanel）+ fx/core.js（esc/fmtDuration）+ fx/llm.js（parseSSE/formatLLMTelemetry）+ ui/usage.js（recordLLMUsage）+ fx/master.js（7 名）。
- **static/js/fx/master.js**：追加 decisionItem / archiveItem（逐字 + 注释）+ window 桥 2 名；元数据 = 阶段 1 时「detail/delete 确认」等函数注释里的「工单 05」编号为阶段 1 编号（保留原义）。DOMAINS 登记 2 名（master.js 块 5→7）。
- **tests/js/master-report-html.test.mjs**（新建，3 test）：decisionItem keep（无 select/含 data-archive/理由）、merge（select + value="proj-b" selected——**注意产物为多行模板字面量，断言用 `（合并[\s\S]*?）`**，初版写死 `（合并）` 曾红）、archiveItem（data-topic/value=2026C/data-unarchive/（无理由））。
- **index.html（apply-04.mjs 一次通过，8853→8272）**：①2 行 host import（usage/master）；②llmPricesDefaults 声明行→注记；③loadSettings 写入点→setter；④母版区段（`// 母版页` → loadChangelog 末 `}`，≈540 行）→6 行注记——搬移前校验 removed span 含 scannedProjects/stagedDirs/distPanel/setStep/renderReport/loadMasters/loadChangelog/masterCache、**不含 collectLlmPrices（防越界进设置簇）**、**含 btn-confirm 监听（防漏搬）**；⑤用量区段（dashes → btn-usage-reset `});`）→6 行注记。ⓘⓘ 校验：35 名零残留定义、makeProgressPanel({ 恰 1 处（只剩 recPanel）、host 调用点（recordLLMUsage(ev)/(data)、renderUsageStats();、loadMasters();、loadChangelog();）都在。
- **tests/js/recommend-telemetry.test.mjs**：蒸馏面板段（distPanel 定义 + startProgress）重指向 ui/master.js（新增 masterJs 读入；html 保留 markup 断言 id="prog-llm-telemetry"）；recPanel/startRecProgress 仍在 host（工单 12 再迁）。
- 验证：node --test 440 全绿；pytest 2465 全绿（bg 确认）；diag 零 EXC（favicon 404 既有噪音）；smoke 11/11；探针 probe-04-master.mjs：两模块动态 import 导出面 ✓ fx 桥 decisionItem/archiveItem ✓ host 无 loadMasters/distPanel/renderReport 定义 ✓ **母版 tab 实况表格渲染 2 行 + master-msg 空（loadMasters 成功）+ prog 域 DOM 在位** ✓ changelog 22 组 ✓ usage DOM + reset 在位 ✓。

## 检查表

- [x] `static/js/ui/master.js`：整区胶水逐字搬移 + export（loadMasters/loadChangelog）+ 头部注释（三层结构、顶层监听 import 时绑定）
- [x] `static/js/ui/usage.js`：用量记录服务前置拆分（recordLLMUsage 等 4 流共享）+ llmPricesDefaults 所有权 + setter
- [x] `static/js/fx/master.js`：decisionItem/archiveItem + 桥 + DOMAINS 登记
- [x] `tests/js/master-report-html.test.mjs`：3 test（补测纯函数）
- [x] index.html：apply-04.mjs（CRLF 感知；2 区段删除 + 3 处适配 + import 2 行；越界/漏搬双钩子）+ 35 名零残留 + 调用点全在
- [x] recommend-telemetry.test.mjs 蒸馏段重指向 ui/master.js
- [x] node --test 440 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + 探针 04（母版 2 行/changelog 22 组/usage 域）通过
- [x] 中文提交 + CHANGELOG 记录

## 风险点 / 跟踪

- 设置页 collectLlmPrices 现经 `import { llmPricesDefaults }`（活绑定只读）取单价——工单 10 迁设置簇时保持同模式或改 getter，记录在工单 10。
- host import 面继续膨胀（fx 19 + app/ui 3 + usage/master 2 名）——收尾工单 20 做最小化核对。
