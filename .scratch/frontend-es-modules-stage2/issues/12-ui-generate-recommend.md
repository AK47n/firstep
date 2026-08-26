# 12 — 生成页 · 推荐/参考选择/模块池/选中/警告/题面 viewer：static/js/ui/generate-recommend.js（含步骤状态核心 ui/step-state.js）

**要做什么：** generate tab 的「步骤 1-3」大簇迁入 `static/js/ui/generate-recommend.js`：题面 PDF viewer + 推荐流（SSE 接收 recPanel / 进度 / 澄清问题）/ 参考文件选择器 / 模块池与推荐结果 / 选中箱 / 警告区 / 平台卡 renderPlatforms / useTopic 题面载入事务。**get 簇拥有 chosenPlatform（含 setChosenPlatform）。** 本票**同时**交付**步骤状态核心 ui/step-state.js**（前置原因见「⚠ 工单序调整」）。 **被谁阻塞：** 02 + 03（progress.js）+ 04（usage.js——recordLLMUsage 在 ui/usage.js，非工单 10）

## ⚠ 工单序调整（2026-08-27，实施中发现；spec.md 已同步）

- **A↔ST 循环**：A（推荐簇）useTopic→markStepDone(1)；ST（步骤簇）restoreDraft→写 chosenPlatform + 调 renderPlatforms/renderSelected/renderWarnings（A 函数）。ESM 循环 import 本身合法（全是函数级引用、无顶层互调），但**模块边界上不存在有效全序**——A 先迁则 markStepDone 不在任何模块可 import；ST 先迁则 A 函数不在任何模块。
- **cut 方案**：ST 拆两半——**ui/step-state.js**（无 A 依赖：STEP_NAV_CARD_SELECTOR / stepCard / markStepDone / markStepUndone / unmarkSteps / syncStep7 / stepDoneSet / STEP_TOTAL / syncStepDone / renderStepProgress / initStepNav IIFE / CARD_COLLAPSE_SELECTOR / initCardCollapse）+ **ST 剩余胶水留 host**（DRAFT 与总览：collectDraftState / scheduleDraftSave / clearDraft / restoreDraft / overviewPlanNow / genOverviewWarn / refreshGenOverview / runOverviewFill / initGenOverview——工单 18 迁，届时从 step-state 与 generate-recommend import）。**A 只需 markStepDone（step-state 提供）；step-state 零 A 依赖 ⇒ 票内同时交付两模块，循环在模块边界内自洽。**
- **工单序变化**：07（library）改挂在本票之后（renderLibraryTable→openModuleInfo / loadLibrary→renderModulePool 两条 A 硬边）；其余顺序不变（07 后 08 reference → 09 topic → 10 settings → 11 recent/readiness → 13-17 其余生成簇 → 18 steps 胶水 → 19 RD → 20 收尾）。

**状态：** resolved（2026-08-27；JS 442 全绿、pytest 2465 全绿、diag 零 EXC、smoke 11/11、probe-12 生成页实况 9/9、probe-draft-12 草稿恢复写点 2/2）

## 实施记录

- **依赖裁定（spec 未覆盖，本票新增接缝——后续工单必读）**：
  1. **模块无法 import host 作用域**——host 内联调用点靠 host 顶部 import 代理（06/11 先例）；模块→host 依赖必须走接缝。
  2. **syncStep7 体读 A/B 状态**（chosenPlatform / expanded(A) / pinBindings / instances(B) + pinRoles()(B 函数)）→ spec「零 A 依赖」不成立 → **参数化 syncStep7(env)**，env = `{platform, expanded, roles, bindings, instances}`（roles 由调用方 pinRoles() 算出）。host 侧 6 调用点逐处传参（renderPinCard ×3 / unbindRole / bindRole / renderGenerateSuccess）。
  3. **syncStepDone 调 refreshGenOverview（host 至 18）+ refreshReadinessPanel（host 至 19）** → step-state 加接缝 `setOnStepChange(fn)`：syncStepDone 内改调 fn()；host 启动区注册 `() => { refreshGenOverview(); refreshReadinessPanel(); }`。18/19 迁出后可继续用注册模式（避免 generate-steps→step-state 环）。
  4. **A 函数引用 B/E/DRAFT（host）9 项** → `setClusterDeps(deps)`（Object.assign 进模块内 clusterDeps）：scheduleDraftSave / updateFixCenterAvailability / resetPinState / resetInstances / clearInstanceTarget / renderInstanceConfig / renderPinCard / loadPinBoard / backfillInstances。host 启动区一次性注册薄胶水（直接调 host 函数/写 host 状态）。工单 13 / 16 / 18 迁出后各票把接缝改静态 import（记录进各自实施记录）。
  5. **restoreDraft 直接赋值 A 状态**（chosenPlatform / selectedSlugs / currentTopicId）→ import 绑定赋值非法 → A 导出 `setChosenPlatform` / `setSelectedSlugs` / `setCurrentTopicId` / `setRecommendClarifications`（readiness 7757 清空澄清历史也用 setter）；restoreDraft 改调四 setter。chosenPlatform 写点全审计结果：定义 2306；写 = renderPlatforms 点击（A 内随迁）+ restoreDraft（→setter）；其余皆只读（含 openModuleInfo 默认参）。
  6. **recordLLMUsage import 自 /js/ui/usage.js**（issue 正文早前写 ui/settings.js 为过时表述，以工单 04 为准）。

- **static/js/ui/generate-recommend.js**（新建 ~750 行，状态所有权表 + 接缝说明头注释）：28 函数 + 12 状态逐字搬移（renderPlatforms / setTopicPdfTextVisible / showTopicPdfViewer / hideTopicPdfViewer / loadTopicPdf / clearTopicSummary / recommendChip / suggestionChip / renderRecommendResult / reRenderAfterSelectionChange / showRecommendError / showRecommendQuestions / recPanel 实例 / startRecProgress / stopRecProgress / startRecommend / referenceAnchorLabel / loadReferencePicker / renderReferencePicker / renderRefSelected / renderReferenceResult / renderModulePool / openModuleInfo / initModuleGrid / addModule / runExpand / renderSelected / renderWarnings / useTopic）；顶层 12 个 addEventListener + initModuleGrid() 调用随迁（import 时绑定，module 延迟执行 DOM 已就绪）。import app.js / fx/{core,platform,module,reference,score,llm,draft}.js / ui/{progress,usage,step-state}.js。
- **static/js/ui/step-state.js**（新建 ~190 行）：STEP_NAV_CARD_SELECTOR / stepCard / markStepDone / markStepUndone / unmarkSteps / syncStep7(env) / stepDoneSet / STEP_TOTAL / syncStepDone / renderStepProgress / initStepNav IIFE / CARD_COLLAPSE_SELECTOR / initCardCollapse + setOnStepChange；import app.js / fx/{draft,generate}.js。零 A 依赖（参数化后成立）。
- **index.html（apply-12.mjs，7944→7061 行）**：①host import 两行（A 21 名代理 + ST 8 名代理）；②全局状态段 A 状态 5 行→注记（instances/instancePinTarget 留 host）；③A 簇主体 2303-3061→注记；④useTopic 6842-6859→注记；⑤ST 核心 7293-7391→注记；⑥ST 进度条 7448-7468→注记；⑦卡片折叠 7769-7814→注记；⑧restoreDraft 三赋值改 setter；⑨readiness recommendClarifications 清空改 setter；⑩syncStep7 六调用点参数化；⑪启动区前 setClusterDeps + setOnStepChange 注册块。校验：28 函数/常量零残留 + 14 状态写点零残留（含 `aria-expanded` 式局部声明白名单豁免）+ syncStep7 参数化恰好 6 处。
- 验证：node --test 442 全绿（结构钉重指向 5 文件：group-cards / recommend-telemetry / step-done-refs / score-points-format / recent-workflows-format——前四个按归属指向 generate-recommend.js，第五个 cache_hit 断言亦指向之；markStepDone(2)/syncStep4( 调用点复核确认归属 A 非 generate-steps）；pytest 2465 全绿（bg）；diag 零 EXC；smoke 11/11；probe-12.mjs 9/9（平台卡点选→步骤 3 dot/chip/进度条、模块池 26 卡、加模块 adc→步骤 6 + 展开 + 引脚卡 body 态、step-nav 12 / 折叠 22 / chips 12、全程零 EXC）；probe-draft-12.mjs 2/2（草稿恢复 setter 写点：平台卡 selected + 步骤 3/6 完成 + 已选清单回填 + 零 EXC）。

## 检查表

- [x] 新建 `static/js/ui/generate-recommend.js`：28 函数 + 状态随簇 + import + export（setChosenPlatform 等 4 setter / useTopic / renderPlatforms / startRecommend / loadReferencePicker / renderModulePool / renderSelected / renderWarnings / renderRecommendResult / openModuleInfo / setClusterDeps + 7 只读状态）+ 头部注释（状态所有权表 / 接缝说明）
- [x] 新建 `static/js/ui/step-state.js`：ST 核心（含 syncStep7 参数化 / setOnStepChange 接缝）
- [x] index.html：apply-12.mjs（CRLF 感知 7 段删除 + import 行 + restoreDraft/readiness 改 setter + syncStep7 六处传参 + 接缝注册块）
- [x] 结构钉重指向：group-cards / recommend-telemetry / step-done-refs / score-points-format / recent-workflows-format
- [x] node --test 442 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + probe-12 生成页实况 + probe-draft-12 草稿恢复写点
- [x] grep 零残留：index.html 无 28 函数定义 / 无 A/ST 状态写点
- [x] 中文提交

## 风险点

- **工单 07（library）前置**：renderLibraryTable / loadLibrary 裸调 openModuleInfo / renderModulePool（5690 / 5747 / 5798 / 7922 一带）——host 顶部 import 代理，07 迁出后改 import 自 generate-recommend.js（spec 已定）。
- **工单 13（pins）前置**：A 内对 B 的 7 项调用走 clusterDeps（host 注册薄胶水写 host 状态）——13 迁出后把 setClusterDeps 注册改为从 generate-pins.js import（或保留 host 胶水转调 import 名）；instances/instancePinTarget 写点并不全在 B（见 13 风险点修正）。
- **工单 18（steps 胶水）**：DRAFT/总览留 host——restoreDraft 已改 setter（本票）；collectDraftState / overviewPlanNow 读 A 活绑定 + runOverviewFill 调 renderRecommendResult（7584 代理）；18 迁出后改 import 自 generate-recommend.js + step-state.js。
- **工单 09（topic）**：useTopic 调用点 6639 / 6698 在 topic 簇（host 代理）——09 迁出后 ui/topic.js import useTopic 自 generate-recommend.js（A 内 clearTopicSummary 失效语义同源）。
- **工单 16（fix）/ 19（readiness）**：updateFixCenterAvailability / refreshReadinessPanel 经接缝——16 / 19 迁出后接缝改静态 import。
