# 01 — 编译判读换闸 + 契约失真对齐（架构评审 2026-08-12 候选 2/4/5 最小实施面）

**What to build:** 架构评审（%TEMP%\architecture-review-20260812-1849.html）核实后裁决的最小改动集：编译「判读」知识已单源在 fix_errors.py（parse_compile_errors / summarize_compile_output，docstring 明令"禁止调用方另写正则"），但两个消费方违规另写正则且已漂移——CLI 验收脚本（-b 增量假绿风险）与前端 fixErrorCount；另有四处已发生的契约失真（事件 docstring 过期 / retry 死分支 / compile_start 无人听 / changelog 示例与正则矛盾）与一处耦合（/api/compile 被 AI 配置门控）。逐一对齐，不引新架构。

**Status:** resolved

**来源：** 架构评审候选卡 2（判读单源）/ 卡 4（契约对偶）/ 卡 5（CLI 换闸）核实后收敛——服务端判读域已单源，本轮只换闸违规消费方 + 对齐失真，不做卡 1（循环入域，需 grilling）与卡 3（匹配剥离，防御性后置）。

## 裁决（2026-08-12 核实后，用户待确认）

| 项 | 裁决 | 理由 |
|---|---|---|
| CLI uv4_build 换闸 | **做** | generate_check.py:131 用 `-j0 -b` 增量 vs 生产 collect_build_log 用 `-j0 -r -b` 全量——autocompile-loop 工单决策 4 明载「-b 增量日志无编译行必须 -r」，脚本正在踩已知坑，验收可能假绿；验收脚本是每工单真机「0 错 0 警」断言的基础 |
| 前端 fixErrorCount 第三份正则 | **做** | index.html:1605-1608 违背 fix_errors.py:170「禁止另写正则」；循环控制流已用 compile.passed（正确），此正则只供轮次文案，换 summary.errors 即可 |
| events.py done 契约 docstring 过期 | **做** | events.py:41-44 未列 duration/parsed_errors/summary（webapp.py:872-877 实际已发射），「词表唯一出处」与实际漂移 |
| retry 死分支 | **做（删）** | fix 流 _retry_parse 不发 retry 事件（llm.py:1005-1014 发 retry 的是蒸馏 _retry_batch）；index.html:1620-1621 分支 + 1452 词表注释误导，实现发事件时再加回 |
| EVENT_COMPILE_START 无人听 | **做（前端补听）** | webapp.py:855 发射、前端 1683-1688 只分支 done/error；补 compile_start 分支（文案与 fetch 前写死的一致），词表真实化 |
| /api/compile AI 配置门控 | **做（解除）** | webapp.py:838 `_require_config` 缺 api_key 即 400，但编译不调 LLM（只须 uv4_path/gmake_path）；无 key 有工具链的用户应能「编译看结果」（修复按钮仍 400 如实报，循环自然停） |
| changelog 示例方括号矛盾 | **做（两行）** | CHANGELOG.md:3 / changelog.py:14 示例 `- [HH:MM]` 与真实数据、正则（`^- (?:(\d{1,2}:\d{2}) )?`）不符，照示例维护会静默解析为 time="" |
| 卡 1 修复会话编排入域 | **不做（本轮），待 grilling** | 真摩擦（轮次状态机在 JS 无 pytest 覆盖），但方向选择（服务端会话 vs 前端抽函数直测 vs 折中）需 grilling，实施面大，另立工单 |
| 卡 3 匹配决策剥离 | **后置** | 真实强耦合但防御性，当前无改匹配规则的进行中场景；下次改匹配规则前再做 |
| 工作根双基准（fix_backup_root vs config 库根） | **不做** | 仅在用户分开配置 module_library_dir 与 masters_dir 时触发；config 域已定案一轮，不重开 |
| GENERATION_GATES 签名统一 | **不做** | 验收路径传空 manifests 是有意选择（该门验证 manifest 声明，生成侧测试已覆盖冲突用例） |

## 实施（文件边界）

1. **`.scratch/real-run/generate_check.py`（uv4_build 换闸，118-138）**：
   - 删自带 `-j0 -b` 命令拼装与 `(\d+) Error\(s\)` 正则、`keil_build.log` 落盘；
   - 改调 `from contest_generator.compile_runner import collect_build_log, find_uv4, compile_passed, summarize_compile_output`（脚本已 import 包内模块先例：30-34）；
   - 工具链发现：`uv4 = find_uv4(os.environ.get("KEIL_UV4") or None)`（保持 env 覆盖语义，走生产候选表）；`build = collect_build_log("stm32", out_dir, uv4=uv4)`；
   - 返回形态不变 `(是否通过, 摘要)`：`passed = compile_passed(build.platform, build.run.exit_code)`；摘要 = `f"UV4 exit={...} {tail}（{summary['errors']} 错误）"`，tail 取 build.run.output 尾行。
2. **`src/contest_generator/static/index.html`**：
   - 删 `fixErrorCount`（1605-1608）；循环 1767 改 `initial.summary.errors`、1791 改 `lastSummary.errors`（for 循环外维护 `let lastSummary = null;`，1773 编译后 `lastSummary = compile.summary;`，语义与 errorText 同步更新）；
   - 1452 词表注释去 `retry /`；fixHandleEvent 删 retry 分支（1620-1621）；
   - runCompileOnce 的 parseSSE 回调（1683-1688）加 `else if (type === "compile_start") { compileBanner("running", "编译中…（第 N/3 轮）"); }`——文案与 fetch 前写死的一致，事件有人消费。
3. **`src/contest_generator/events.py`（41-44）**：done 契约 docstring 补展示层字段——`duration（秒）/ parsed_errors（[{path,line,message}]）/ summary（{errors,warnings}）`，注明与 webapp.py:828-833 docstring 同源。
4. **`src/contest_generator/webapp.py`（/api/compile）**：`_require_config(context)`（838）改 `_current_config(context)`（编译只须工具链路径；路由内 uv4_path/gmake_path 读取不受影响）；docstring 补一句「不要求 AI 配置」。回滚路由（798）不动（回滚不调 LLM 但属修复面，保持现状）。
5. **`CHANGELOG.md:3` + `src/contest_generator/changelog.py:14`**：示例 `- [HH:MM] 描述` → `- HH:MM 描述`（与真实数据、_ITEM_RE 对齐）；docstring 9-10 行「带 `HH:MM` 时间前缀」已对，不动。
6. **不动**：fix_errors.py / llm.py / compile_runner.py / sse.py / 生成器 / 门禁。

## 验收

- [x] `pytest` 全绿（1242 = 基线 1241 + 1）+ `mypy src` 干净（36 files）+ index.html node 语法过（内联 JS node --check OK）
- [x] 真机：`uv4_build` 对既有 2026C stm32 产物跑一次——命令与生产同闸 `('C:\Keil5\Core\UV4\UV4.exe', '-j0', '-r', '-b', ...)`，日志 18 条 compiling 行 + linking + `".\Objects\Project.axf" - 0 Error(s), 1 Warning(s).`，`-o` 临时文件在 %TEMP%（不落工程目录）；passed=True（exit=1 = 有警告无错，compile_passed 域语义），摘要 `UV4 exit=1 ...（0 错误）`
- [x] 契约：清 config.json api_key（备份恢复）→ 起服务 → `POST /api/compile` 流式 `compile_start` → `done`（passed=true / summary {errors:0, warnings:1} / duration 3.2s），之前 400「未配置 AI API」不再出现
- [x] changelog：`GET /api/changelog` 200，8 组，首条 `2026-08-12` 组 11 条、首条 time `00:04`（格式正常，示例去方括号后与 _ITEM_RE 一致）
- [ ] 前端：浏览器验收修复中心横幅（编译中 → 成功/失败/超时四态不回归）——数据面已验（compile_start 事件入流 + done 四态载荷与 renderCompileBanner 契约不变），视觉待用户浏览器

## 实施记录

2026-08-12 实施（本会话直接执行）：

- `.scratch/real-run/generate_check.py` uv4_build 换闸：删 `-j0 -b` 命令拼装 + `(\d+) Error\(s\)` 正则 + keil_build.log 落盘；改调 `find_uv4(os.environ.get("KEIL_UV4") or "")`（env 覆盖语义，走生产候选表；ticket 原文 `or None` 会崩——find_uv4 签名 `override: str` 不接受 None）+ `collect_build_log("stm32", out_dir, uv4=uv4)` + `compile_passed` / `parse_compile_errors` / `summarize_compile_output`（后两个在 fix_errors.py——ticket 原文写 compile_runner 有误，该模块是叶子模块不 import fix_errors）；CompileRunnerError → `(False, str(exc))`（保持「工程里没有 .uvprojx」硬失败语义）；docstring 内 `\d` 转义（非 raw 字符串 + 契约测试 ast.parse 会发 SyntaxWarning，红证：改前 5 warnings 改后 2，均为第三方 fastapi/httpx）
- `index.html`：删 fixErrorCount（1605-1608）+ 两处调用改 `lastSummary`（循环外 `let lastSummary = initial.summary || null;` 与 errorText 同步，1773 编译后更新，null/非有限值守卫保持「多条报错」兜底文案）；词表注释去 `retry /` + fixHandleEvent 删 retry 死分支（蒸馏层才发 retry）；runCompileOnce parseSSE 加 compile_start 分支（文案与 fetch 前写死一致，事件有人消费）
- `events.py`：compile done 契约 docstring 补展示层字段（duration / parsed_errors / summary），注明与 webapp /api/compile docstring 同源
- `webapp.py` /api/compile：`_require_config` → `_current_config`（config None 时 uv4_path/gmake_path 覆盖为空走自动探测），docstring 补「不要求 AI 配置（编译不调 LLM，只须工具链路径；修复按钮仍走 AI 配置校验）」；回滚路由不动
- `CHANGELOG.md` + `changelog.py`：示例 `- [HH:MM] 描述` → `- HH:MM 描述`（与真实数据 / _ITEM_RE 对齐）；CHANGELOG.md 追加本工单条目（19:32）
- `tests/test_webapp.py` +1：`test_compile_without_ai_config_streams_done`（config=None 起 app + 假 UV4 → compile_start → done，passed=true + summary {0,0}；红证：改前该形态 400）
- 不动：fix_errors / llm / compile_runner / sse / 生成器 / 门禁（diff 仅上述 7 文件）
