# 16 — 生成页 · 编译修复工坊：static/js/ui/generate-fix.js

**要做什么：** generate tab 的「编译修复（fix center）」簇迁入 `static/js/ui/generate-fix.js`（FIX_MAX_ROUNDS / toolchains / fixLoop + 单次编译 / 修复循环 / 批继续 / 横幅 / 结果表 / telemetry 展示 / 就绪度）。**被谁阻塞：** 02（app.js）

**状态：** 已实施（resolved）

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数/常量/对象（4654-5229）：FIX_MAX_ROUNDS const 4654 / toolchains 4657 / fixLoop 4658 / compileBanner 4665 / fmtSeconds 4672（**纯函数 → fx 候选**：迁 fx/generate.js 或 fx/core.js + 补测；或保留本簇——裁定：纯计算无 DOM → 迁 fx 并补 1-2 条单测）/ renderCompileBanner 4677 / fixKeyOf 4692 / fixKeyBasename 4695 / maincScrollToRange 4710 / maincJumpToLine 4728 / fixToggleSource 4755 / fixRenderResults 4788 / fixSetBusy 4837 / fixCenterBusy 4843 / renderToolchainStatus 4850 / renderFixLLMTelemetry 4859 / clearFixLLMTelemetry 4865 / updateFixCenterAvailability 4871 / fixHandleEvent 4878 / runCompileOnce 4932 / runFixOnce 4971 / fixRounds 5007 / startFixCenter 5080 / continueFixCenter 5141。
- ⚠ **pytest 结构钉**：tests/test_generate_check_contract.py L578-581 断言 index.html 含 `const FIX_MAX_ROUNDS`、L621 钉 `fixLoop.resume`——重指向 ui/generate-fix.js。
- 依赖：`$` / handle / apiPost / apiGet（app.js）；fx/generate.js（isConflictError / genStageTexts / fmtWait）+ fx/llm.js（usage/parseSSE——fixHandleEvent 内解析 SSE）+ fx/code.js（maincScrollToRange? 是胶水——fx/code.js 的 maincLineOffsetRange 供 maincScrollToRange）；reportRecentStatus（ui/recent.js）；recordLLMUsage / formatLLMTelemetry（ui/settings.js? fx/llm.js——formatLLMTelemetry 在 fx/llm.js，renderFixLLMTelemetry 用它）。
- markup：btn-fix-center / btn-fix-continue / fix-status / fix-center-round / fix-errors-msg / fix-errors / fix-telemetry 等 id（markup 不动）。

## 检查表

- [x] 新建 `static/js/ui/generate-fix.js`：上述件逐字搬移 + import（app.js / fx/generate.js / fx/llm.js / fx/code.js / ui/recent.js / ui/settings.js（recordLLMUsage））+ export（startFixCenter / continueFixCenter / runCompileOnce / runFixOnce / fixRounds / renderToolchainStatus / updateFixCenterAvailability / FIX_MAX_ROUNDS / fixLoop）+ 头部注释
- [x] fmtSeconds 迁 fx（fx/generate.js，纯）+ 补测（1-2 条：秒→X.Ys 格式契约）+ fx-guard DOMAINS 登记；index.html 无 fmtSeconds 定义
- [x] pytest test_generate_check_contract.py：三个结构钉重指向本文件
- [x] index.html：CRLF 感知行区间删除（4654-5229 内目标名；**物理升序**）+ 顶部 import 行追加
- [x] `node --test` 全绿 + pytest 全绿 + diag 零 EXC + smoke 11/11 + 修复区实况（就绪态渲染 + 前置守卫）
- [x] grep 零残留：index.html 无 `function startFixCenter(` / `const FIX_MAX_ROUNDS` 等定义
- [x] 中文提交

## 实施记录（工单 16）

### 行号复核（grep 起止锚；工单 12-15 删除后前移）
簇体实际位于 2474-3039（修复中心 section 注释 → 修订与深化 section 注释，不含后者）：FIX_MAX_ROUNDS 2482 / toolchains 2485 / fixLoop 2486 / compileBanner 2493 / fmtSeconds 2500 / renderCompileBanner 2505 / fixKeyOf 2520 / fixKeyBasename 2523 / maincScrollToRange 2538 / maincJumpToLine 2556 / fixToggleSource 2583 / fixRenderResults 2616 / fixSetBusy 2665 / fixCenterBusy 2671 / renderToolchainStatus 2678 / renderFixLLMTelemetry 2687 / clearFixLLMTelemetry 2693 / updateFixCenterAvailability 2699 / fixHandleEvent 2706 / runCompileOnce 2760 / runFixOnce 2799 / fixRounds 2835 / startFixCenter 2908 / continueFixCenter 2969 + 4 监听器（btn-fix-center / btn-fix-continue / btn-fix-errors / btn-fix-rollback）+ continue 文案。issue 正文行号（4654-5229）为阶段 1 时代编号。

### 搬迁边界与接缝裁定（关键决策）
- **ui/generate-fix.js（602 行 LF）**：25 函数/常量/对象 + 4 监听器顶层绑定（import 时绑，DOM 已就绪）；`toolchains` 改 `export let`——**注意：不可同时行内 export + 尾部 export 清单**（工单 15 的 Duplicate export 教训重演，diag 抓到后改纯声明）；新增 `setToolchains(v)` setter（写入经 setter，读取方 import 活绑定）。
- **fmtSeconds 纯计算 → fx/generate.js**（`export function` + window 桥补齐）+ fx-guard DOMAINS 登记 `fmtSeconds: "fn"` + tests/js/fmt-seconds.test.mjs（2 条：有限非负 → 1 位小数；非有限/负/非数字 → "0.0" 兜底）。
- **修复中心服务接缝回退**：工单 15 的 `setGenerateCoreDeps`（startFixCenter / compileBanner / toolchainsGet）→ **静态 import**（core 顶部 `import { startFixCenter, compileBanner, toolchains } from "/js/ui/generate-fix.js"`；renderGenerateSuccess 3 处还原为直接引用；core 导出面去 setGenerateCoreDeps；host 2246 import 行去该名 + 3951 注册行删除）。
- **toolchains 主写簇 = generate-fix**：host 两处写点改 setter——setSettingsDeps 回调（`toolchains = ts` → `setToolchains(ts)`）与 init（`toolchains = state.toolchains` → `setToolchains(...)`）；host 顶部 import `renderToolchainStatus / setToolchains / updateFixCenterAvailability`。
- **A↔fix 无环**（照工单 13 pins 先例）：fix 单向 import A 的 `chosenPlatform / selectedSlugs`（状态读方 import）；A 对 fix 的服务调用（updateFixCenterAvailability）**仍经 host 启动区 setClusterDeps 闭包**（host 3389 注册行不变）。generate-recommend.js 头部注释同步更新。
- **导出面（12 名）**：检查表 9 名 + toolchains / setToolchains / compileBanner（host 与 generate-core 实际使用）；host import 行只列 host 用到的 3 名（其余为核心模块间静态 import，不经 host）。

### 结构钉重指向（tests/test_generate_check_contract.py）
三处读体从 _index_html() 改 _fix_src()（新增 helper，读 ui/generate-fix.js）：①`const FIX_MAX_ROUNDS` 钉（L577-582）；②「可点「继续修复」再来」文案钉（L606-611）；③`fixLoop.resume = { errorText, lastSummary, lastFixDone }` 快照钉（L614-621）。btn-fix-continue 按钮 id 钉（L598-603）留 html——markup 未动。

### 验证矩阵（全绿）
- node --test "tests/js/*.test.mjs"：**444/444**（442 + fmt-seconds 2 条）。
- python -m pytest -q：**2465 passed**（3 warnings 既有噪声）。
- diag.mjs：零 EXC（favicon 404 既有噪声）；中途曾报 `Duplicate export of 'setToolchains'`（export function 声明 + 尾部清单重复）→ 已修。
- smoke.mjs：11/11。
- probe-16.mjs：13/13（动态 import 导出齐全 / 工具链状态文案 ✅✅ / 就绪度：清草稿后未选平台禁用 → 选平台启用 / btn-fix-center 真实点击前置守卫「请先生成工程」/ btn-fix-continue 文案「再来 3 轮」/ generate-core → generate-fix 静态 import 链假载荷：横幅 fail|编译失败（假目录 400——startFixCenter 经静态 import 触达）/ 全程零 EXC）。
- grep 零残留：27 名（含 fmtSeconds）在 index.html 无定义；`$("btn-fix-center").addEventListener` 等监听已在模块。

### 探针教训（追加）
- ①`export let`/`export function` + 尾部 `export {...}` 清单 = Duplicate export（同工单 15 的 setGenerateCoreDeps）——**新模块一律「纯声明 + 尾部清单导出」**；②探针就绪态前须清 localStorage draft（restoreDraft 会恢复平台选择，破坏「未选平台」前提）；③webapp 静态服务与磁盘曾有短暂不一致窗口（diag 旧事件误报回归）——以 Invoke-WebRequest 对比为准。

## 风险点

- toolchains 归属：写点 = init 9021（host）→ 本票把 init 内 `toolchains = state.toolchains` 改调 `setToolchains(...)`（本模块导出）或本模块导出 `toolchains` 经 host import 后赋值（**import 绑定不可赋值** → 必须 setter）。实施时按最小改动裁定并记录。
- fixLoop 是可变对象（对象属性写合法——`import { fixLoop }` 后属性写 OK；`fixLoop = {...}` 整换则非法 → 用对象属性写或 setter）。结构钉 L621 保持 `fixLoop.resume` 断言（import 后对象属性可读）。
- fixHandleEvent 内 parseSSE 用例（sse-parser.test.mjs 浏览器同构）——本簇 imports 不破坏。
