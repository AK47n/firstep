# Spec：前端 DOM 胶水按 tab 拆分（阶段 2）

> 继任：.scratch/frontend-es-modules/spec.md（阶段 1：纯函数 ES 模块化）。阶段 1 已合入 main（c1a5f33 收尾，18 个 fx 模块 + fx-guard.test.mjs 护栏 + 167 个已搬名称）。本 spec 处理其「火候控制」中明确推迟的**阶段 2（DOM 胶水按 tab 拆）**。
> 立项评估（用户已拍板）：立项 YES。范围 = 本 spec + 全部工单 + 实施 01 补漏票。generate 大簇按子功能拆 8 个模块；未测纯函数（truncate / fmtSeconds / fmtClock / fmtDuration / decisionItem / archiveItem）迁入 fx 模块并顺带补轻量单测。

## 问题陈述

阶段 1 完成后，`src/contest_generator/static/index.html` 主体 `<script type="module">`（2214-9043 行，约 6830 行）仍含 **274 个函数定义**——全部是 DOM 胶水（render / load / 事件绑定 / SSE 工作流），与 18 个 fx 模块的 import 行同处一文件。维护税：

- 单文件 6830 行内联胶水，按 tab 混杂：8 个 tab（generate / library / reference / pdf / topic / master / changelog / settings）的代码按物理位置交错，AI/人导航性差；
- 胶水与纯函数边界靠约定维持（新纯函数须落 fx），但胶水本身无文件边界，回迁/混编无护栏约束；
- 事件接线 100% `addEventListener`（click 188 / input 20 / change 20 / keydown 19 / remove 12 / scroll 3 / resize 2 / pagehide 1），**0 个内联 onclick 属性**——HTML 标记无需任何改动即可拆模块（最大有利条件）。

## 方案

把 DOM 胶水按 **tab 域 + 共享件** 拆为独立 ES 模块，浏览器原生 ESM + 静态挂载 `/js`（阶段 1 已有 `app.mount("/js", StaticFiles(...))`，无需改动 webapp.py）：

- `static/js/app.js`：跨 tab 共享壳（`$` / `handle` / `apiGet` 等 / 主题 / `KIND_TEXT` / toast / `state` 所有权 / tabId 会话）；
- `static/js/ui/<域>.js`：每 tab 一个（或一个簇）的 DOM 胶水模块；
- `static/js/ui/progress.js`：共享进度面板（推荐 recPanel 与母版提炼 distPanel 共用，阶段 1 盘点确认）；
- `static/js/ui/files.js`：模块库/参考库共用的「文件行增删 + 读取」件；
- `static/js/fx/*.js`：纯函数区（阶段 1 既定；本阶段新增未测纯函数迁入并补测）；
- `index.html` host 保留：fx imports + app.js import + 各 ui 模块 imports + 页签分发器 + 启动 IIFE + init\* 调用（目标 ~150 行）。

### 桥接约定（沿用阶段 1 升级版，index.html 主体 module 顶部静态 import）

1. index.html 主体 `<script type="module">` 顶部静态 `import { ... } from "/js/app.js"` 与 `import { ... } from "/js/ui/<域>.js"`——module 语义保证被 import 模块先求值再跑主体，调用点零改动、时序零等待；
2. ui 模块内部：`import { $, apiGet, state, ... } from "/js/app.js"`；同域兄弟函数直接引用；跨域函数 import（如题库 `useTopic` 归生成推荐簇，题 tab 按钮 import 调用）；
3. **禁止环规则**：app.js 不得 import 任何 ui 模块；ui 模块之间允许单向依赖；跨簇 mutable 状态按「主写簇拥有、读方 import」裁定（见下）；
4. ui 模块**不挂 window 桥**（window 同名桥是阶段 1 fx 兼容层，供探针/devtools 取纯函数；ui 探针改用 import 或 DOM 实况）；
5. 新纯函数一律写入 fx 模块（约定不变）；渲染/胶水函数写入对应 ui 模块。

### 共享 mutable 状态归属裁定（已逐处盘点）

| 状态 | 写方 | 裁定 |
|---|---|---|
| `state`（含 `state.modules` 属性写 @5800/5850/5960 等） | refreshState 2345 + init 9009 两处直接赋值；其余全是属性写 | 归 app.js；ui 模块 `import { state }` 后属性写合法（ESM 绑定，0 改写） |
| `chosenPlatform`（2361） | renderPlatforms 点击 2376 + restoreDraft 8452（两簇） | 归推荐簇 A；A 导出 `setChosenPlatform(v)`，steps 簇 restoreDraft 改调 setter |
| `stepDoneSet`（8483） | markStepDone / markStepUndone / unmarkSteps / syncStepDone（均 steps 簇） | 归 steps 簇；读方（readiness / 页签分发器 host）import |
| `toolchains`（4657） | init 9021 写入 | 随编译修复簇 E（renderToolchainStatus 同簇）；或改读 `state.toolchains`——实施时按最小改动裁定 |
| `currentTopicId` / `topicPdfTextVisible` | useTopic 7238 等 | useTopic 事务整体归推荐簇 A；题 tab 按钮 import 调用 |
| `llmPricesDefaults`（2336） | collectLlmPrices 8162 | 归 settings 簇 |
| `usageBase` 8952 / `usageSessionAcc` 8953 / USAGE_STORE_KEY 8950 | settings 簇 | 归 settings 簇（usage 统计） |
| pin 系列 + LED_COLORS / PIN_TYPE_STYLE / PIN_TYPE_ZH / MODULE_COLORS | 板图簇 B | 归 B |
| `stagedDirs` 7339 / `scannedProjects` 7337 / `currentReport` 7338 | 母版簇 | 归 M |
| `topicRows` 6926 / `topicEntries` 6971 | 题库簇 | 归 T |
| `recPanel` const 2735 | 推荐簇 | 归 A；distPanel 7415 / PHASE_LABEL 7413 / MAX_LOG_LINES 7414 归 M（事件回调是 M glue 专属调用点） |

### 跨簇边（每票实施时以 grep 复核，记录进实施记录）

- useTopic（T）→ A：`markStepDone(1)` / `$("problem")` / `clearTopicSummary` / `loadTopicPdf` / toast / 切 generate tab；
- refreshState（app）→ renderPlatforms：app.js 内调会成环——把该调用拆到 host 启动（init 内 refreshState + renderPlatforms 并列），行为不变；
- renderGenerateSuccess（D）→ refreshRecent（RE）；fixHandleEvent（E）→ reportRecentStatus（RE）；
- readinessState（RD）→ `stepDoneSet.has(5)`（ST）；
- restoreDraft（ST）→ renderPlatforms / renderSelected / renderWarnings（A）+ `setChosenPlatform`；
- 页签分发器（host 保留）→ 各 tab `load*` 函数（host import）；
- init\*（host 启动）→ 各模块 init 函数。

### 工单序调整（2026-08-27，实施中发现）

- **A↔ST 循环事实**：A（推荐簇）useTopic→`markStepDone(1)`；ST（步骤簇）restoreDraft→写 chosenPlatform + 调 renderPlatforms / renderSelected / renderWarnings（均 A 函数）。ESM 循环 import 合法（函数级引用、无顶层互调），但**模块边界上不存在有效全序**：A 先迁则 markStepDone 无可 import；ST 先迁则 A 函数无可 import。
- **cut 方案（已定）**：ST 拆两半——**ui/step-state.js**（步骤状态核心，零 A 依赖：STEP_NAV_CARD_SELECTOR / stepCard / markStepDone / markStepUndone / unmarkSteps / syncStep7 / stepDoneSet / STEP_TOTAL / syncStepDone / renderStepProgress / initStepNav IIFE / CARD_COLLAPSE_SELECTOR / initCardCollapse）与 **ST 剩余胶水**（DRAFT + 总览：collectDraftState / scheduleDraftSave / clearDraft / restoreDraft / overviewPlanNow / genOverviewWarn / refreshGenOverview / runOverviewFill / initGenOverview——留 host，工单 18 迁，届时 import step-state 与 generate-recommend）。**step-state 与 generate-recommend 在同一票（12）同时交付**，循环在模块边界内自洽；A 仅从 step-state import markStepDone。
- **工单序变更**：07（library）改挂工单 12 之后（renderLibraryTable→openModuleInfo、loadLibrary→renderModulePool 两条 A 硬边）；其余顺序不变（08 reference → 09 topic → 10 settings → 11 recent/readiness → 13 pins → 14 mainc → 15 core → 16 fix → 17 revise → 18 steps 胶水 → 19 readiness → 20 收尾）。
- chosenPlatform 写点全审计：renderPlatforms 点击（A 内，随迁）+ restoreDraft（ST，工单 18 改 `setChosenPlatform`）+ **实施 12 时 grep `chosenPlatform\s*=` 逐一处理主体残留写点**（import 绑定只读——但 host 内 `chosenPlatform =` 写点若存在须即刻改 setter 或交由 A 提供 setChosenPlatform）。

## 用户故事

1. 作为维护者，我想要每个 tab 的 DOM 胶水独立成文件，以便 6830 行单文件按域消解、AI 可导航性上升。
2. 作为维护者，我想要 index.html 主体只剩 imports + 页签分发 + 启动，以便单文件阅读负担降到 ~150 行。
3. 作为维护者，我想要未测纯函数迁入 fx 模块并获得轻量单测，以便「被测试纯函数一律在 fx、零字符串提取」的约定闭合。
4. 作为维护者，我想要迁移后页面行为零变化（无构建 / 无打包 / 无新增依赖 / HTML 标记零改动），以便本地工具保持打开即用。
5. 作为维护者，我想要既有 434 个 JS 测试 + pytest 在迁移后原样通过（仅结构钉重指向新模块），以便回归信号可信。
6. 作为维护者，我想要 fx-guard 护栏继续兜底纯函数单源（新迁入 fx 的名称登记进 DOMAINS），以便双源回退不可能发生。

## 实现决策

- **模块布局**：`static/js/app.js` + `static/js/ui/{progress,files,library,reference,pdf,topic,master,settings,recent,generate-recommend,generate-pins,generate-mainc,generate-core,generate-fix,generate-revise,generate-steps,generate-readiness}.js`；pure 件进 `static/js/fx/`（workflow.js 新建；core.js 增 truncate；format 件按域就近：fmtSeconds→fx/generate.js、fmtClock/fmtDuration→fx/progress.js（新）或 fx/core.js、decisionItem/archiveItem→fx/recent.js 或 fx/master.js——实施时以「被谁测试/被谁引用」就近裁定并记录）。
- **每票标准动作**（沿用阶段 1，已固化）：
  1. CRLF 感知行区间删除脚本删除 index.html 定义（`$order` 必须按 grep 出的文件物理位置**升序**，末键单独收尾；end 锚点兼容「`}` + 空行 + 锚 | `}` + 直接锚」双形态）；
  2. 新建 `ui/<x>.js` 逐字搬移 + 域内状态/常量随簇 + 头部注释（依赖 / 状态所有权 / 源自工单号）；
  3. index.html 主体 module 顶部追加对应 import 行；
  4. 结构钉测试重指向新模块（断言内容不改，目标文件换）；
  5. `node --test "tests/js/*.test.mjs"` 全绿 + `pytest` + diag.mjs 零 EXC（防悬空签名→主体 SyntaxError）+ smoke.mjs 11/11 + 该 tab 实况探针；
  6. grep 零残留（`function <名>(` 在 index.html 无定义）；
  7. 中文提交信息（`.githooks/commit-msg` 拒绝英文）。
- **删除脚本纪律**（阶段 1 教训）：先 grep 定位全部 start 行 → 按物理升序构造删除数组 → 0-based 边界校验（prev/next 锚 + content 抽样比对）→ 删除前 `git diff --stat` 检查行数变化一致 → 编辑后必跑 diag。
- **结构钉重指向清单**（断言语义不变、目标文件换新模块）：

| 测试 | 钉 | 新目标 |
|---|---|---|
| tests/js/group-cards.test.mjs | 推荐区接线 | ui/generate-recommend.js |
| tests/js/step-done-refs.test.mjs | markStepDone(2) / syncStep4( 调用点 | ui/generate-recommend.js（工单 12 重指向：cut 方案复核后非 generate-steps） |
| tests/js/score-points-format.test.mjs | renderScorePointPanel(scorePoints) 调用点 | ui/generate-core.js |
| tests/js/recommend-telemetry.test.mjs | recPanel / startRecProgress 接线 | ui/generate-recommend.js |
| tests/js/btn-icons.test.mjs | initBtnIcons + `[data-ico]` 选择器 | app.js |
| tests/js/price-reference-clear.test.mjs | renderPriceReference 函数体（tbody 是 markup 不动） | ui/settings.js |
| pytest tests/test_generate_check_contract.py | `const FIX_MAX_ROUNDS`（L578-581）/ fixLoop.resume（L621） | ui/generate-fix.js |

  不动：topic-cards（#topic-grid 容器 = markup）、topic-detail（CSS 类 = markup）、generate-overwrite（CONFLICT_MSG_PREFIX 单源断言保持 index.html 无定义）；fx-guard DOMAINS 表本阶段只增不减。
- **验收命令**：`node --test "tests/js/*.test.mjs"`（glob 形式，Node 24 目录形式报 MODULE_NOT_FOUND）+ `pytest` + diag + smoke。
- **火候控制**：
  - 不做 StoreAdapter（架构评审候选④）——仅若 `state` 读写面证明需要最小 setter，允许加 `setState` 单点；
  - 不做 DOM 抽象层 / 组件化 / 事件委托框架；
  - 不引入任何构建工具链 / npm 依赖 / 打包器 / 测试框架（轻量单测沿用 node:test）；
  - 不改 HTML 标记、不改 CSS、不改后端 Python（webapp.py/llm.py 等一律不动；结构断言内的 python 测试只改重指向）；
  - 搬移中发现的行为 bug 记 `.scratch/backlog.md`，不并入本阶段工单；
  - 每票后浏览器冒烟该 tab；全量冒烟在收尾工单统一做。

## 测试决策

- 什么是好测试：既有 434 个 JS 测试（416 + 护栏 18）与 pytest 全量在迁移后原样通过；仅结构钉把「index.html 断言」重指向「新模块文件」；新迁入 fx 的纯函数各补 1-2 条轻量单测（node:test，沿用既有断言风格）；
- 将测试哪些模块：每个 ui 模块的验收 = 对应 tab 实况渲染探针 + 零 EXC + 全绿回归；fx 新件的测试 = 新 test 文件或并入既有文件；
- 既有先例：阶段 1 每票 416 全绿基线；v5 结构测试（`not hasattr` 防回退）+ grep 唯一出处验证。

## 范围外

- StoreAdapter（候选④）、webapp.py 拆域（候选①）、llm.py 包化（候选③）——均明确不做；
- 平台适配接缝、v5 其余候选；
- 任何构建 / 依赖 / 打包；
- HTML 标记与 CSS 改动（含 id 改名、class 改名）；
- 后端 Python 结构改动；
- 阶段 1 已迁 fx 模块的再组织（除非本阶段新纯函数就近落位）。

## 补令说明

- 单人项目、纯搬家、行为零变化——同阶段 1 与 v5 master-decompose 先例。
- 本 spec 的切片计划（20 票）以工单文件为准，实施时函数清单以 grep 为准（阶段 1 经验：标题数字系估计，实施记录会修正）。
