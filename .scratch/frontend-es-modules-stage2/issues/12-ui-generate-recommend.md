# 12 — 生成页 · 推荐/参考选择/模块池/选中/警告/题面 viewer：static/js/ui/generate-recommend.js

**要做什么：** generate tab 的「步骤 1-3」大簇迁入 `static/js/ui/generate-recommend.js`：题面 PDF viewer + 推荐流（SSE 接收 recPanel / 进度 / 澄清问题）/ 参考文件选择器 / 模块池与推荐结果 / 选中箱 / 警告区 / 平台卡 renderPlatforms / useTopic 题面载入事务。**get 簇拥有 chosenPlatform（含 setChosenPlatform）。** **被谁阻塞：** 02 + 03（progress.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数（2477-3135 + 2362 + 7234）：renderPlatforms 2362 / setTopicPdfTextVisible 2477 / showTopicPdfViewer 2484 / hideTopicPdfViewer 2515 / loadTopicPdf 2522 / clearTopicSummary 2574 / recommendChip 2611 / suggestionChip 2617 / renderRecommendResult 2637 / reRenderAfterSelectionChange 2700 / showRecommendError 2707 / showRecommendQuestions 2713 / recPanel const 2735（makeProgressPanel 实例 + events 回调：round/converged/cache_hit/llm_telemetry/done/question/error）/ startRecProgress 2789 / stopRecProgress 2800 / startRecommend 2805 / referenceAnchorLabel 2850 / loadReferencePicker 2858 / renderReferencePicker 2866 / renderRefSelected 2905 / renderReferenceResult 2927 / renderModulePool 2941 / openModuleInfo 2952 / initModuleGrid 2975 / addModule 2994 / runExpand 3002 / renderSelected 3022 / renderWarnings 3092 / useTopic 7234。
- 状态：selectedSlugs 2337 / expanded 2338 / pythonTemplates 2339 / warnings 2340 / scorePoints 2341 / chosenPlatform 2361 / recProblem / lastRecommend / recommendClarifications / selectedReferenceIds / autoReferenceIds / referenceEntries / currentTopicId / topicPdfTextVisible（写=useTopic / viewer）——**chosenPlatform 写点**：renderPlatforms 点击 2376 + restoreDraft@8452（steps 簇，改调 `setChosenPlatform`）。
- 跨簇边：recPanel events 调 recordLLMUsage（settings 簇，工单 10 已迁——import）；formatLLMTelemetry（fx/llm.js）；renderRecentList 无；startRecommend POST /api/recommend 用 apiPost + apiGet（app.js）；useTopic 调 markStepDone(1) / toast / clearTopicSummary / loadTopicPdf（模块内）+ `$("problem")`（markup）+ 切 generate tab（host 分发逻辑——`document.querySelector('[data-tab="generate"]').click()`）。
- 主题：initTheme / applyTheme 已在 app.js（工单 02）；`KIND_TEXT` 若本簇使用，import app.js。
- 结构钉：group-cards.test.mjs（推荐区接线→本文件）、recommend-telemetry.test.mjs（recPanel/startRecProgress 接线→本文件）、step-done-refs.test.mjs 的 syncStep4( 调用点（勾选变更在 reRenderAfterSelectionChange?——grep 复核调用点归属，若在本文件则钉重指向本文件而非 steps——**实施时精确核对**）。

## 检查表

- [ ] 新建 `static/js/ui/generate-recommend.js`：上述函数+状态逐字搬移 + import（app.js / fx/topic.js（useTopic 用 topicDetailHTML?等）/ fx/module.js / fx/llm.js / fx/core.js / ui/progress.js / ui/settings.js（recordLLMUsage））+ export（含 setChosenPlatform / useTopic / renderPlatforms / startRecommend / loadReferencePicker / renderModulePool / renderSelected / renderWarnings / renderRecommendResult）+ 头部注释（状态所有权表）
- [ ] index.html：CRLF 感知行区间删除（2362-3135 内目标名 + 7234 useTopic；**物理升序**；避开 app.js/fx 已迁名）+ 顶部 import 行追加
- [ ] restoreDraft（steps 簇，工单 18 迁）改 `setChosenPlatform(d.platform)`——本票先提供 setter；steps 未迁期间主体内 restoreDraft 裸改 chosenPlatform 需在主体 import 后被同名绑定接管（**注意**：主体内 `chosenPlatform = ...` 赋值在 import 绑定下非法！→ 本票把主体中 restoreDraft 的赋值改调 setter（或其他簇写点同步改），实施时 grep 全部 `chosenPlatform =` 写点逐一处理）
- [ ] 结构钉重指向：group-cards / recommend-telemetry /（step-done-refs 按复核结果）
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 生成页实况探针（推荐区渲染 + 模块池 + 平台卡）
- [ ] grep 零残留：index.html 无 `function startRecommend(` 等定义
- [ ] 中文提交

## 风险点

- **chosenPlatform 写点全审计**（grep `chosenPlatform\s*=`）：renderPlatforms 2376（本簇内，随迁无碍）、restoreDraft 8452（改 setter）、其他（如 openModuleInfo 默认参——只读，无碍）。
- recPanel 实例化在模块顶部（const，import 时求值）——makeProgressPanel 内若顶层执行 DOM 查询（timerTotalId 等），模块求值时机 = import 时（defer 后 body 已在）→ 成立；冒烟验证。
- 本簇是最大一票（~790 行 + 状态），删除脚本分段执行，每段后 diag。
