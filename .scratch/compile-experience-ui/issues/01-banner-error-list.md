# 01 — 编译体验展示层：结果横幅 + 结构化错误列表 + 点击展开源码行

**What to build:** 编译闭环的**展示层升级**（用户真机从未遇到编译出错、生成即过，修复逻辑零改动）：① 生成结果区顶部显眼**编译结果横幅**（编译中 / 成功「0 Error 0 Warning · 耗时 Xs」/ 失败「N 错误 · 耗时 Xs」/ 无工具链灰条提示），让"自动编译发生了、结果如何"一眼可见；② 编译失败时**结构化错误列表**（文件:行 + 消息 + 状态标签：待修复/已修复/跳过/新增），点击条目**展开对应源码行**（新薄接口读输出目录文件，展示修复后的当前行）；③ 每轮编译**耗时**展示（后端计时，横幅 + 轮次条）。范围外：编译命令/超时、工具链探测、修复逻辑、3 轮循环状态机、回滚、生成器——全部不动。

**Status:** resolved（2026-08-12 实施完成：1230 绿 + mypy 干净 + node 语法过 + sse-parser 9/9；真机 8001 源码行接口三路 400/200 实测通过，前端四态待用户浏览器验收）

## 决策记录（grilling 2026-08-12，用户确认）

1. **方向收敛**：用户从未遇到过编译错误（生成即过）→ 修复闭环（成功率/轮数/批量）不是痛点，本次只做**展示层**；编译速度/增量编译不做（Keil `-b` 增量是历史真机坑，CCS 侧收益不确定，Q3 用户无感）。
2. **结果横幅（Q5/Q9 a）**：放**生成结果区顶部**（res-* 卡片最前，不在第 10 栏内——太靠底，违背"生成完一眼确认"）；状态含「编译中（当前轮次）」「成功（错误数/警告数/耗时）」「失败（错误数/耗时）」「无工具链灰条（未检测到工具链，跳过自动编译）」。**无工具链也要显眼提示**——用户问"是自动还是手动"说明现状存在感为零。
3. **自动编译保持自动（Q6 a）**：触发时机/条件不动（有工具链生成后自动触发），只增强状态可见性。
4. **耗时（Q7 a）**：后端计时（编译域 RunResult 加 duration，time.monotonic 包子进程，含超时场景如实记录），done 载荷透传；横幅 + 轮次条「第 N/3 轮 · 耗时 Xs」展示。
5. **结构化错误列表（Q4/Q8 a）**：`/api/compile` done 加 `parsed_errors`（复用 fix_errors.py 现有 `parse_compile_errors`——**单一来源，禁止复制正则**）+ `summary {errors, warnings}`（数字：UV4 优先抓汇总行 `N Error(s), M Warning(s)`；无汇总行（CCS/gmake）退行级计数——warning 判定用 `"warning" in message.lower()`，**零正则改动**）；列表条目点击展开源码行（新接口，薄实现，见实施 3），展示**修复后的当前行**。
6. **范围**：后端 = `/api/compile` done 载荷扩展 + 新源码行接口 + duration；前端 = `index.html`（横幅 + 列表渲染改造 + 交互）。**不动**：compile_runner 编译命令/超时/探测、fix_errors 修复逻辑与契约（parsed[]/fixes[] 向后兼容只增不改）、llm.py、sse.py、3 轮循环状态机（FIX_MAX_ROUNDS）、backup/rollback、生成器、库数据。

## 实施

1. **compile_runner.py**：编译结果（RunResult 或等价物）加 `duration` 字段（`time.monotonic()` 包 `subprocess.run`；超时分支也记录实际耗时），docstring 同步。不动命令/超时/探测。
2. **fix_errors.py**：加纯函数 `summarize_compile_output(error_text, parsed_errors) -> dict`（或等价命名）——先试 UV4 汇总行正则 `(\d+)\s+Error\(s\)(?:,\s*(\d+)\s+Warning\(s\))?`，命中即用（errors/warnings 都取汇总值）；未命中退行级：`len(parsed)` 为底，warning 条数 = `"warning" in e.message.lower()` 计数，errors = 总数 − warnings。垃圾文本 → `{errors: 0, warnings: 0}`。与 `parse_compile_errors` 同文件（解析域单源），不动既有解析函数。
3. **webapp.py**：
   - `/api/compile` done 载荷**追加**（不改既有字段，前端向后兼容）：`duration`（秒，float）、`parsed_errors`（`[{"path","line","message"}]`，由 `parse_compile_errors(error_text)` 构造——**与 /api/fix-errors 的 parsed 同源同构**）、`summary`（`{"errors","warnings"}`，summarize_compile_output）。
   - 新接口 `POST /api/compile/source-line`：请求 `{output_dir, path, line}` → 200 `{path_resolved, line_text}`（`line_text` 为第 line 行的内容，含行尾不强制；取修复后的当前文件）；404/400 中文（errors.py 登记文案）。**路径安全**：复用 fix_errors 的路径解析逻辑（`_report_benchmarks` 双基准：.uvprojx/.cproject 父目录 + output_dir 根）与 containment 校验——resolve 后必须在 output_dir 内，逃逸（`../..` 穿越）拒绝；文件不存在 / line 越界 → 400 中文。文档注释同步（参照 /api/compile 的注释风格）。
4. **index.html**：
   - 新元素 `#compile-banner` 放**生成结果区第一个卡片顶部**（res-* 区，实施者按布局就近放置）：状态类（running/success/fail/notool），初始 hidden。文案：「编译中…（第 N/3 轮）」「编译成功 · E Error W Warning · 耗时 Xs」「编译失败 · N 个错误 · 耗时 Xs」「未检测到工具链，跳过自动编译（可在设置页填 uv4_path / gmake_path）」。数据接 `startFixCenter` 循环事件（compile done / fix-errors done 事件已在前端流中，横幅状态从这些事件驱动，**不动循环状态机本身**）。
   - `#fix-results` 渲染升级：纯文本 div 行 → **可点击条目列表**。每条：[状态标签] `path:line` 消息。状态映射：`fixes[].status==='applied'` → 「已修复」；`skipped` → 「跳过」；无对应 fix 的 parsed → 首轮「待修复」、后续轮「新增」（key = 归一化 path + line，path 归一 POSIX + basename 兜底；无法匹配的 fixes 单独列出）。**首编失败（无 fixes 数据）也要渲染**——数据来自 compile done 的 `parsed_errors`。
   - 点击条目 → `fetch /api/compile/source-line` → 条目下展开一行源码（`N: 代码`，等宽字体，可折叠再点收起；加载结果缓存，重复点击不重复请求）。失败（400/404）→ 条目旁显示原因文案。
   - 耗时展示：横幅 + 轮次条 `#fix-center-round` 追加「耗时 Xs」。
   - 语法检查兼容：改完跑 node 语法检查（沿用现有检查方式）。
5. **测试（红证先行）**：
   - `summarize_compile_output` 单测：UV4 汇总行（0 Error 1 Warning / 3 Error 5 Warning 取汇总值）、UV4 无汇总行退行级、CCS（gmake/armclang）error + warning 行计数、垃圾文本空安全。
   - `/api/compile` done 载荷断言：新增字段存在且结构正确（parsed_errors 与 fix-errors parsed 同构、summary 数字、duration > 0）——**红证**：实施前断言失败。
   - 新接口单测：命中返回行内容；`..\` 双基准形态（uvprojx 在子目录）命中；containment 逃逸（`..\..\`）400；文件不存在 400/404；line 越界 400。
   - 既有测试零回归（parsed[]/fixes[] 契约未改）。
6. **不动**：llm.py / sse.py / compile_runner 命令与超时 / 工具链探测 / FIX_MAX_ROUNDS 与循环状态机 / backup / rollback / 生成器 / 库数据 / test_llm.py。

## 验收标准

- [x] pytest 全绿（1230，+14）+ `mypy src` 干净（35 files）+ node 语法过（内联 JS node --check + sse-parser 9/9）
- [x] summary 单测：UV4 汇总行优先（含真机无逗号形态）、CCS 行级计数、空安全（红证：实施前 ImportError / 断言失败已验）
- [x] /api/compile done 载荷含 duration / parsed_errors / summary（红证先行：实施前字段缺失断言失败已验）
- [x] 源码行接口：双基准命中（`..\` + uvprojx 在 user/）、逃逸拒绝、越界 400、line 参数校验（缺失/非数字/0 → 400）
- [x] 前端：横幅四态（running/success/fail/notool）齐、错误列表可点击展开（fixRenderResults + /api/compile/source-line + 缓存）、首编失败也有列表（round 0 待修复）、耗时显示（横幅 + 轮次条）；结构测试零改动（不动循环状态机）
- [ ] 真机验收：真实生成 stm32 工程（有工具链）→ 横幅「编译成功 · 0 Error 0 Warning · 耗时 Xs」；注入错误 → 错误列表 + 点击展开源码行 + 修复状态标签；删除工具链路径 → notool 灰条（无工具链分支）
- [ ] 修复闭环零回归：真机注入错误走完整循环（≤3 轮）行为与现状一致（只多展示，不改行为）

## 实施记录（2026-08-12）

- compile_runner.py：CompileRun 加 `duration: float`（time.monotonic 包子进程调用，超时分支如实记录；UV4 -o 日志采集重构处透传）。命令/超时/探测零改动。
- fix_errors.py：+`summarize_compile_output(error_text, parsed) -> {errors, warnings}`——UV4 汇总行正则 `(\d+)\s+Error\(s\)(?:[,\s]+(\d+)\s+Warning\(s\))?`（标准带逗号与真机无逗号形态都命中，Warning 段缺省按 0），命中即取汇总值（与行级计数不一致以汇总为准）；未命中退行级 len(parsed) 为底 + `"warning" in message.lower()` 计数；垃圾/空文本 → {0,0}。+`resolve_source_path`（_resolve_in_root + _report_benchmarks 双基准的公开接缝，展示层与修复域共用同一套路径判决）。
- webapp.py：/api/compile done 只追加 duration / parsed_errors（parse_compile_errors 同源同构，与 fix-errors parsed 字段集一致）/ summary；新接口 POST /api/compile/source-line（薄同步端点：双基准 + containment，文件不存在/越界/行号越界 → FixError 400 中文，line 参数校验 → HTTPException 400）。
- index.html：`#compile-banner` 置生成结果区第一卡片顶部（#generate-result 首子元素，四态 CSS 深色主题）；JS 新增 compileBanner/fmtSeconds/renderCompileBanner/fixKeyOf/fixKeyBasename/fixToggleSource/fixRenderResults；runCompileOnce 起流前 running（第 N/3 轮）→ done/error 后终态；fixHandleEvent apply_result 改可点击行、done 按 parsed+fixes 重建（待修复/已修复/跳过/新增 + 无法匹配 fixes 单列）；startFixCenter 首编失败即渲染列表、轮次条追加耗时、无工具链 early-return 打 notool 横幅；btn-generate 无工具链 else 分支打 notool 横幅。
- 测试：test_fix_errors.py +6（summarize 单测）、test_webapp.py +8（done 载荷 2 + 源码行接口 6），红证先行（实施前 ImportError / 404 / 断言失败已验）。
- 真机（8001）：重启服务后 curl/urllib 实测 /api/compile/source-line——`..\` 双基准命中 200 {path_resolved, line_text}、line 越界 400「行号越界：…（文件共 3 行）」、`..\..\` 穿越 400「源码文件不存在或路径越界」。前端四态/展开交互待用户浏览器验收（无工具链分支：删 uv4_path 后重新生成/点按钮 → 灰条）。

## 文件边界

- **改**：`src/contest_generator/compile_runner.py`（RunResult duration）、`src/contest_generator/fix_errors.py`（+summarize_compile_output）、`src/contest_generator/webapp.py`（/api/compile 载荷 + 新源码行接口）、`src/contest_generator/static/index.html`（横幅 + 列表交互 + 耗时）、`tests/`（编译/修复/接口相关测试文件 + 红证用例）、`.scratch/compile-experience-ui/issues/01-banner-error-list.md`（本工单）
- **不动**：llm.py / sse.py / 编译命令与超时 / 工具链探测 / 循环状态机（FIX_MAX_ROUNDS）/ backup / rollback / 生成器 / 库数据 / 素材库
