# 16 — 生成页 · 编译修复工坊：static/js/ui/generate-fix.js

**要做什么：** generate tab 的「编译修复（fix center）」簇迁入 `static/js/ui/generate-fix.js`（FIX_MAX_ROUNDS / toolchains / fixLoop + 单次编译 / 修复循环 / 批继续 / 横幅 / 结果表 / telemetry 展示 / 就绪度）。**被谁阻塞：** 02（app.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数/常量/对象（4654-5229）：FIX_MAX_ROUNDS const 4654 / toolchains 4657 / fixLoop 4658 / compileBanner 4665 / fmtSeconds 4672（**纯函数 → fx 候选**：迁 fx/generate.js 或 fx/core.js + 补测；或保留本簇——裁定：纯计算无 DOM → 迁 fx 并补 1-2 条单测）/ renderCompileBanner 4677 / fixKeyOf 4692 / fixKeyBasename 4695 / maincScrollToRange 4710 / maincJumpToLine 4728 / fixToggleSource 4755 / fixRenderResults 4788 / fixSetBusy 4837 / fixCenterBusy 4843 / renderToolchainStatus 4850 / renderFixLLMTelemetry 4859 / clearFixLLMTelemetry 4865 / updateFixCenterAvailability 4871 / fixHandleEvent 4878 / runCompileOnce 4932 / runFixOnce 4971 / fixRounds 5007 / startFixCenter 5080 / continueFixCenter 5141。
- ⚠ **pytest 结构钉**：tests/test_generate_check_contract.py L578-581 断言 index.html 含 `const FIX_MAX_ROUNDS`、L621 钉 `fixLoop.resume`——重指向 ui/generate-fix.js。
- 依赖：`$` / handle / apiPost / apiGet（app.js）；fx/generate.js（isConflictError / genStageTexts / fmtWait）+ fx/llm.js（usage/parseSSE——fixHandleEvent 内解析 SSE）+ fx/code.js（maincScrollToRange? 是胶水——fx/code.js 的 maincLineOffsetRange 供 maincScrollToRange）；reportRecentStatus（ui/recent.js）；recordLLMUsage / formatLLMTelemetry（ui/settings.js? fx/llm.js——formatLLMTelemetry 在 fx/llm.js，renderFixLLMTelemetry 用它）。
- markup：btn-fix-center / btn-fix-continue / fix-status / fix-center-round / fix-errors-msg / fix-errors / fix-telemetry 等 id（markup 不动）。

## 检查表

- [ ] 新建 `static/js/ui/generate-fix.js`：上述件逐字搬移 + import（app.js / fx/generate.js / fx/llm.js / fx/code.js / ui/recent.js / ui/settings.js（recordLLMUsage））+ export（startFixCenter / continueFixCenter / runCompileOnce / runFixOnce / fixRounds / renderToolchainStatus / updateFixCenterAvailability / FIX_MAX_ROUNDS / fixLoop）+ 头部注释
- [ ] fmtSeconds 迁 fx（fx/generate.js，纯）+ 补测（1-2 条：秒→X.Ys 格式契约）+ fx-guard DOMAINS 登记；index.html 无 fmtSeconds 定义
- [ ] pytest test_generate_check_contract.py：两个结构钉重指向本文件
- [ ] index.html：CRLF 感知行区间删除（4654-5229 内目标名；**物理升序**）+ 顶部 import 行追加
- [ ] `node --test` 全绿 + pytest 全绿 + diag 零 EXC + smoke 11/11 + 修复区实况（开工一次或就绪态渲染）
- [ ] grep 零残留：index.html 无 `function startFixCenter(` / `const FIX_MAX_ROUNDS` 等定义
- [ ] 中文提交

## 风险点

- toolchains 归属：写点 = init 9021（host）→ 本票把 init 内 `toolchains = state.toolchains` 改调 `setToolchains(...)`（本模块导出）或本模块导出 `toolchains` 经 host import 后赋值（**import 绑定不可赋值** → 必须 setter）。实施时按最小改动裁定并记录。
- fixLoop 是可变对象（对象属性写合法——`import { fixLoop }` 后属性写 OK；`fixLoop = {...}` 整换则非法 → 用对象属性写或 setter）。结构钉 L621 保持 `fixLoop.resume` 断言（import 后对象属性可读）。
- fixHandleEvent 内 parseSSE 用例（sse-parser.test.mjs 浏览器同构）——本簇 imports 不破坏。
