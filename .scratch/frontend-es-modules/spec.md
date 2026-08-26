# Spec：前端纯函数 ES 模块化（架构评审候选 2 · 阶段 1）

> 来源：架构评审报告 architecture-review-20260826-204159.html（候选 2：index.html 8900 行单文件 → 静态 ES 模块），必要性评估结论：「②阶段 1（纯函数模块化 + 测试改 import）必要性中上 = 唯一值得立项」。用户拍板「可以，把值得做的做了」。
> 先例：.scratch/architecture-deepening-v5/issues/01-master-decompose.md（同构手法：纯搬家、行为零变化、结构测试防回退、grep 唯一出处验证、docstring 全保留）。

## 问题陈述

前端单文件 `src/contest_generator/static/index.html`（11141 行）内含约 8900 行内联脚本；154 个被测试的纯函数（渲染子串 / 过滤 / 排序 / 状态计算）与 267 处 DOM 事件绑定、425 个函数混杂在同一作用域。44 个 `tests/js/*.test.mjs` 通过**字符串提取**复用这些函数：其中约 24 个文件用括号配平的 `extract(name, deps)`（每份文件复制整套提取代码），约 16 个文件用正则 `match(/function X[\s\S]*?\n\}/)`。该机制的维护税：

- 44 份重复的提取器代码；测试文件头部 ≈30-70 行纯基建；
- 重命名函数 = 测试悄然变「未找到」（`assert.ok` 只断言存在，不提示真正原因）；
- 被测试函数**不得引用模块级常量**（否则提取体缺符号），代码结构为此长期扭曲——这是一笔已在持续支付的税；
- 两种提取变体并存（括号配平 vs 非贪婪正则），后者对含 `}\n` 的函数体更脆。

## 方案

把全部**被测试的纯函数**从 index.html 内联脚本迁出为**独立的 ES 模块文件**（`src/contest_generator/static/js/fx/<domain>.js`），测试改为直接 `import`。浏览器侧通过「window 同名惰性桥」保持内联脚本的调用点零改动；DOM 胶水（render/load/事件绑定）本轮**不动**（阶段 2 再按 tab 拆）。无构建步骤、无打包器、无 npm 依赖：浏览器原生 ESM + webapp 静态挂载 `/js`。

## 用户故事

1. 作为维护者，我想要测试直接 `import { pdfFilterEntries } from ".../fx/pdf.js"`，以便不再维护 44 份字符串提取副本。
2. 作为维护者，我想要重命名一个纯函数失败时立刻得到明确的 Module/ReferenceError 而非「未找到函数体」的模糊断言，以获得可靠的回归信号。
3. 作为维护者，我想要纯函数可以自由引用模块级常量（常量随函数进模块），以便代码结构不再为可测性扭曲。
4. 作为维护者，我想要每个 UI 域的函数有独立文件，以便单文件 8900 行的阅读负担随迁移逐步下降、AI 可导航性上升。
5. 作为维护者，我想要迁移后页面行为零变化（无构建 / 无打包 / 无新增依赖），以便本地工具保持打开即用。
6. 作为维护者，我想要迁移后新写的纯函数一律落入 fx 模块（约定），以便单源结构不回退。
7. 作为维护者，我想要一张结构护栏测试断言「已搬函数不再出现在 index.html 定义处」，以防未来再出现双源。

## 实现决策

- **模块位置与格式**：`src/contest_generator/static/js/fx/<domain>.js`（ES module 语法：`export function ...`）；同目录 `src/contest_generator/static/js/package.json` = `{"type": "module"}`（node 端把该目录 .js 视为 ESM；浏览器端 `<script type="module">` 加载，MIME text/javascript 由系统 mimetypes 提供，无需构建）。
- **桥接约定**（每个 fx 模块头部注释声明）：
  1. 模块导出纯函数（只接受数据、返回数据；允许引用同模块兄弟函数与本模块常量）；
  2. **主体脚本 module 化（实施升级，01 工单已验证）**：index.html 主体 `<script>` 改为 `<script type="module">`，文件顶部静态 `import { ... } from "/js/fx/<domain>.js"`——module 语义保证 fx 先加载执行再跑主体，DOM 胶水内裸引用即模块作用域绑定，时序零等待、调用点零改动、顶层立即执行/IIFE 无需改造；
  3. 模块尾部仍保留 `if (typeof window !== "undefined") Object.assign(window, { fn1, fn2, ... })`（**兼容层**：探针脚本 / devtools 按全局名取用仍可用，如 probe 系的 `window.step7DoneState`）；
  4. index.html 内联脚本**删除**已搬函数的定义（单源，无转发别名）；
  5. 被搬函数引用的模块级常量随函数搬入模块并 export（测试注入面收敛），常量**不得**同时保留内联定义（双源即漂移）；
  6. 新纯函数一律写入 fx 模块；渲染/事件胶水函数留在主体脚本（阶段 2 迁移对象）；已搬函数的内联调用点不需要任何改动。
- **后续域工单执行方式**（01 已验证的标准操作）：① 建 `fx/<domain>.js`（逐字搬定义 + 域内常量 + import 共享件 + export + window 桥）→ ② index.html 删除该域函数定义 + 主体模块顶部加对应 import 行 + 注释改「已迁至 static/js/fx/*.js」→ ③ 对应 .test.mjs 删字符串提取改 import → ④ `node --test "tests/js/*.test.mjs"` 全绿。不再需要为每个域添加 `<script type="module" src>` 标签（import 链自动加载）。
- **模块文件划分（最终形态，按 UI 域聚类）**：
  - `fx/core.js`：esc、formatSize（跨域共享的通用件）
  - `fx/env.js`：envRowHTML / envChannelHTML / envCheckStatusHTML（+ ENV_BADGE_GLYPH）
  - `fx/pdf.js`：pdf 域 21 函数 + formatMtime（+ 域内常量）
  - `fx/reference.js`：ref 域 17 函数 + referencePlatformChip（+ 域内常量）
  - `fx/topic.js`：topic 域 17 函数
  - `fx/master.js`：master 域 6 函数
  - `fx/module.js`：模块库域（moduleBadges / pythonArtifactSummary / moduleGrid* / moduleInfoHTML / lib* / moduleRowHTML / editDescStatus / groupCards 6 函数 / 多实例 3 函数 等）
  - `fx/generate.js` + `fx/overview.js` + `fx/recent.js` + `fx/readiness.js` + `fx/draft.js` + `fx/score.js` + `fx/llm.js` + `fx/settings.js` + `fx/code.js` + `fx/btn-icon.js` + `fx/platform.js`：生成流程 / 概览 / 最近任务 / 就绪检查 / 草稿 / 评分清单 / LLM 用量与遥测 / 设置折叠 / C 代码工具 / 图标 / 平台点击（实施时按函数行号与测试文件归属就近归域；模块清单以工单为准，可微调）。
- **静态服务**：webapp.py `create_app` 内新增 `app.mount("/js", StaticFiles(directory=STATIC_DIR / "js"), name="js")`（STATIC_DIR = Path(__file__).parent / "static"，webapp.py:213）；import 增 `from fastapi.staticfiles import StaticFiles`。
- **index.html 加载**：`<script type="module" src="/js/fx/<domain>.js">` 置于内联脚本之后（</body> 前）；module 语义 deferred，任何用户交互前必已执行。
- **测试改造**：`.test.mjs` 头部删除 `html` 读入 + extract()/match()（连同各自变体），改为 `import { ... } from "../../src/contest_generator/static/js/fx/<domain>.js"`（相对路径，与现有 readFileSync 的 `../../src/...` 同层级）。函数调用点不变。
- **特殊情形**：settings-collapse 等「先抽既有核心块（供 syncCollapseBtn）再拼同一 Function 作用域」的拼接法，模块化后改为跨模块 import（核心块函数迁入对应域模块即可）。
- **验收命令（Windows 下必须用 glob）**：`node --test "tests/js/*.test.mjs"`（目录形式在 Node 24 报 MODULE_NOT_FOUND，勿用）；全量 `pytest`。
- **防回退护栏**：最后一张工单新增 `tests/js/fx-guard.test.mjs`：枚举全部已搬函数名，断言 index.html 不含其 `function <name>(` 定义（防双源回退），并从 fx 模块 import 断言其存在。
- **火候控制**：本 spec 只做阶段 1。阶段 2（DOM 胶水按 tab 拆）、候选①（webapp 拆域）、候选③（llm.py 包化）、候选④（StoreAdapter）均明确不做。

## 测试决策

- 什么是好测试：不改动任何既有断言语义——所有 416 个 JS 测试在迁移后原样通过（仅导入方式变化）；「子串断言防脆」等既有纪律延续。
- 将测试哪些模块：迁移中的每个 fx 模块（其对应 .test.mjs 整文件改 import 后全绿即是验证）。
- 既有先例：44 个 .test.mjs 现状；v5 结构测试（`not hasattr` 防回退）与 grep 唯一出处验证。

## 范围外

- DOM 胶水/事件绑定按 tab 拆分（阶段 2），index.html 8900 行脚本主体不动；
- webapp.py create_app 拆分（候选①）；llm.py 包化（候选③）；四库 StoreAdapter（候选④）；
- 任何构建工具链 / npm 依赖 / 打包器引入；
- 后端 Python 结构改动（webapp.py 仅新增一个 4 行 mount）；
- 平台适配接缝、llm 层收敛等 v5 其余候选。

## 补充说明

- 单人项目（近 300 提交 100% AK47n）：收益定位为**维护税削减 + AI/人导航性**，非多人协作解耦；迁移一律**纯搬家、行为零变化**（同 v5 master-decompose 先例）。
- 每张工单以「一个或一组 fx 模块文件 + 涉及测试文件」为切片，张张可独立验证（对应测试全绿 + grep 零残留 + 浏览器冒烟一次）。
- 迁移顺序按域从独立小域到核心大域：core/env 起步（pilot 验证桥接约定），pdf → reference → topic → master → module → generate → 其余 → 护栏收尾。
