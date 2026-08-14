# 01 — generate_check CLI 修复循环对齐（编译失败自动喂修复 ≤3 轮）

**What to build:** CLI 真机验收（`.scratch/real-run/generate_check.py`）与 web 一条龙语义对齐：真机编译失败后不再只报 fail——自动把编译输出喂 `/api/fix-errors`（SSE）→ 重编译验证，≤3 轮，与前端修复中心同语义（编译 → 修复 → 重编译，第 3 轮后如实报告剩余错误）。mspm0 线 gmake 段已由 mspm0-build-makefiles/01 落地（`gmake_build`），本工单在其上补循环。

**Status:** resolved（验收全勾；PR #61 已合 main 28bbcdb——2026-08-14 收尾改正状态字段）

**Blocked by:** mspm0-build-makefiles/01 合 main（PR #59）——本工单的 mspm0 修复循环建立在 `gmake_build` 之上；stm32 侧可先行开发验证。

## 现状证据（2026-08-13 已核实）

- web 有循环（index.html `startFixCenter`，≤3 轮 + 停滞文案），CLI 只有单次编译：`generate_check.py` `check_topic` 编译段一次 `uv4_build`/`gmake_build`，失败即 `ok = False` 收工。
- `/api/fix-errors` SSE 端点已存在（parse_done → fix_start → apply_result… → done/error），CLI 的 `recommend_stream` 已示范同款 SSE 消费写法（词表由 tests/test_generate_check_contract.py 强制与 events.py 一致）。

## 决策记录（代决，用户可 grilling）

1. **轮数上限 3 与 web 一致**（index.html `FIX_MAX_ROUNDS = 3`）；CLI 自持常量 `FIX_MAX_ROUNDS = 3` 并注释指向前端常量（改动须同步——契约测试尽量钉：读 index.html 文本断言两处一致，实施时若读前端文本别扭则退为注释约定，测试只钉 events 词表）。
2. **停滞检测本工单不做**（fix-loop-progress/01 属前端循环，CLI 循环独立实现最小语义：3 轮内 passed 即出活，0 applied 也走完）——两工单并行无依赖；若 fix-loop-progress/01 先合，实施者可顺手同步（applied==0 即停，一行之差），不强制。
3. **payload 复用现有变量**：output_dir（产物目录）、error_text（编译输出原文）、problem_text（题面）、platform、slugs（推荐结果）、main_c（骨架结果）——check_topic 内已有全部变量，零新输入；不带 previous_fixes（本工单不依赖 fix-loop-progress/01，其请求体字段可选向后兼容）。
4. **fix_stream() 消费 SSE**：仿 recommend_stream（buf 拼帧、词表 = fix 事件：parse_done / fix_start / apply_result / done / error，终端 = done / error），返回 done 载荷；契约测试补 fix 事件词表断言（与 events.py 一致，改词表忘改 CLI 即红——recommend 词表既有机制平移）。
5. **输出逐条打印**：每轮打印"第 N/3 轮：X 条 Error → AI 修复…"+"应用 Y 处 / 跳过 Z 处"（fixes 逐条 file:line status reason），与 web 结果列表同信息量；最终通过打印 ✓、3 轮后剩错打印 ✗ + 剩余错误数（summary 单源，不另写正则——既有约定）。
6. **范围外**：停滞检测（见决策 2）、回喂、贴文本手动模式 CLI 化。

## 实施

1. **`.scratch/real-run/generate_check.py`**：
   - `fix_stream(payload)`：POST /api/fix-errors（SSE）→ done 载荷（含 fixes / backup_id / parsed / degraded）；error 终态如实打印并返回失败。
   - `build_fix_payload(...)`：组装请求体（output_dir / error_text / problem_text / platform / slugs / main_c——服务端契约见 webapp `/api/fix-errors` docstring，字段恒发、缺省不放）。
   - `run_fix_loop(out_dir, error_text, ...)`：≤3 轮——fix_stream → 统计 applied/skipped → 重编译（`uv4_build` / `gmake_build`）→ passed 出活 / 仍错下一轮喂最新报错；3 轮后如实报告。返回是否通过。
   - `check_topic` 编译段接入：编译失败 → 打印"进入修复循环" → run_fix_loop；通过则原"✓"输出、失败则 ok=False。
2. **`tests/test_generate_check_contract.py`**：补 fix 事件词表断言（CLI 分支词表 == events.py 常量，recommend 同款机制）；补 `build_fix_payload` 字段集契约（若 recommend payload 已有字段集双强制先例，同款照搬）。
3. **不动**：src 全部（本工单纯 CLI 侧，与 fix-loop-progress/01 并行零冲突）。

### 实施注

- SSE 消费注意：fix 流分钟级（真实 DeepSeek），timeout 给足（recommend_stream 已是 600s 先例）。
- 循环内每轮之间产物目录文件被真实写回（apply_fixes 落盘 + 备份在 ~/.contest_generator/fix-backups/）——CLI 打印备份编号（done.backup_id），用户可回滚。

## 验收标准

- [x] pytest 全绿（含契约测试新增）+ `mypy src` 干净（CLI 脚本不在 mypy src 范围，node 无涉）
- [x] 真机：2026C stm32 注错（或构造缺头文件错误）→ `generate_check 2026C` 修复循环 ≤3 轮内 UV4 0 错，打印逐条应用结果；再跑未注错 2026C 回归首编即过循环不启动
- [~] 真机：mspm0 线注错 → gmake 修复循环闭环（依赖 T1 已合 main）——循环机制闭环，端到端 0 错闭环被 src 侧既有缺口阻断，已立跟进工单（见验收记录）
- [x] 回归：默认双题 2026C/2021F 全绿
- [x] `git status` 只出现预期文件（generate_check.py + test_generate_check_contract.py + 本工单文件 + 跟进工单文件）

## 实施注（2026-08-13）

- 改动面：`.scratch/real-run/generate_check.py` + `tests/test_generate_check_contract.py`，src 零改动（与 fix-loop-progress/01 并行零冲突）。
- generate_check.py 新增：
  - `FIX_MAX_ROUNDS = 3` 常量（注释指向 index.html 同款常量，契约测试钉两处文本一致——决策 1 的"尽量钉"落地为 re 断言，不别扭）；
  - `fix_stream(payload)`：POST /api/fix-errors SSE 消费（recommend_stream 同款 buf 拼帧写法；词表 = parse_done / fix_start / apply_result / done / error，终端 = done / error，apply_result 逐条结果以 done 载荷 fixes 单源为准），返回 `{"event", "data"}`；HTTP 4xx（如输出目录不存在）与流中断（OSError——2026-08-13 真机观察到并行会话服务重启导致 SSE 流被重置，ConnectionResetError ⊂ OSError）如实转 error 终态，不打断验收主流程（recommend_stream 无此兜底，本函数循环 3 轮不该一轮断线就抛栈）；
  - `build_fix_payload(...)`：六字段契约（output_dir / error_text 必填 + problem_text / platform / slugs / main_c 可选上下文——check_topic 内恒有、恒发，缺省不放；不带 previous_fixes，服务端可选向后兼容）；
  - `run_fix_loop(out_dir, error_text, problem_text, platform, slugs, main_c)`：≤3 轮——轮次文案错误数 summary 单源（summarize_compile_output，不另写正则）→ fix_stream → done.fixes 逐条打印（✓/· file:line [status] reason，与 web 结果列表同信息量）+ 应用/跳过计数 + degraded 提示 + backup_id 打印 → 重编译（uv4_build / gmake_build）→ passed 出活 / 仍错喂最新报错原文；3 轮后如实报告剩余错误数。停滞检测未做（决策 2，0 applied 也走完）。
- 编译函数换型：uv4_build / gmake_build 返回 (passed, 摘要, 编译输出原文)——原文供修复循环回喂（与 web /api/compile done 的 error_text 同款"原样采集"契约）；工具链不可用返回 (None, 原因, "")。check_topic 编译段：失败 → 打印"进入修复循环" → run_fix_loop，仍败 ok=False。
- tests/test_generate_check_contract.py +5（17 passed）：
  - fix 事件词表断言（AST 抽取 fix_stream 事件分支 == events.py 修复段常量，recommend 同款机制平移）；
  - build_fix_payload 字段集双强制（全输入恰六字段 / 缺省恰两必填键 / 空可选缺省不放）；
  - CLI FIX_MAX_ROUNDS == index.html 前端常量（决策 1 钉）。
- 真机教训：并行会话共享 8000 端口，SSE 分钟级流会被对端服务重启打断（首跑 2026C 推荐流即被 ConnectionResetError 打断）——真机验收需自起服务并留意端口归属；这直接促成了 fix_stream 的 OSError 兜底。

## Comments

### 验收记录（2026-08-13，真机证据）

- **pytest 1314 绿**（worktree @dc4fed9；合 main 后全量复跑见下）+ `mypy src` 37 文件干净。
- **2026C stm32 注错修复循环（验收第 2 项复验，`check_2026C_inject_t3.log`）**：一次性驱动 `_t3_inject_check.py`（跑完即删）对干净产物 main.c 注入 `t3_injected_missing_fn();` → UV4 首编 exit=2（1 错误）如预期 → `run_fix_loop` 第 1/3 轮 AI 应用修复（`✓ main.c:144 [applied]`，移除注入行）→ 重编译 UV4 exit=0（0 错误）闭环。
- **2026C 干净回归（`check_2026C_t3.log`）**：推荐 2 轮 done（7 模块）→ 门禁全过 → UV4 exit=0 0 错误；首编即过、修复循环未启动（"进入修复循环"零出现）。
- **2021F 干净回归（`check_2021F_t3b.log`）**：推荐 4 轮 done（6 模块：digit_uart/motor/pid/led_beep/zigbee_uart_key/zigbee_uart，含两车无线通信需求的双 zigbee 双选）→ 门禁全过 → UV4 exit=0 0 错误。
- **预算漏洞发现（本工单范围外，已并入 recommend-speedup/01 工单 D 棱镜）**：2021F 首跑（20 条澄清映射）`192486 字节 > 131072` 预检拦死（3 次重试同尺寸 = 确定性）；根因 = `REFERENCE_FULLTEXT_CAP = 60000` 字符 ≈ 180KB 单段上限 > `MAX_REQUEST_BYTES = 128KB` 总量上限，模型点名大参考文件时必现。重跑改用 12 条历史映射通过（该跑推荐流未触发全文点名超限）。修复方案见 `.scratch/recommend-speedup/issues/01-round-trim.md` D 棱镜（cap 60000→35000 + 澄清历史段截断 + 结构测试）。
- **mspm0 线（验收第 3 项 [~]）**：循环机制闭环；端到端 0 错被 src 侧 gmake 报错路径定位缺口阻断（`../main.c` 相对 Debug/ 工作目录、`_resolve_in_root` 两种基准都越界 → 三轮降级 0 applied）——已立跟进工单 `.scratch/gmake-fix-path-resolution/issues/01-gmake-error-path.md`（解析域修复，web 修复中心 mspm0 线同病）。
- 澄清映射：2021F 用 12 条历史映射（`.scratch/real-run/clarify_2021F.json`）；找回的 20 条合并映射留档 `.scratch/real-run/clarify_default.json`（12 历史 + 8 新增，20 条全量随请求体发送会触发上述预算漏洞，待 D 修复后可全量启用）。

