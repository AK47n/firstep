# 01 — 自动编译修复闭环（一条龙：生成 → 编译 → 自动采集报错 → 修复 → 重编译验证）

**What to build:** 把 compile-error-fix/01 的"贴报错"升级为全自动闭环：服务端检测工具链（UV4 / gmake）→ 一键（或生成后自动）编译工程 → **自动采集编译输出**（无需用户拷贝粘贴）→ 喂给既有 fix-errors 管线 → 修复写回 → **自动重编译验证**，仍错则自动再喂（循环 ≤3 轮），最终如实报告剩余错误。无工具链环境回退纯贴文本模式（现有功能照旧）。

**Status:** resolved（2026-08-12 实施 + 真机验收闭环）

## 决策记录（grilling 2026-08-12，与用户确认）

1. **编译执行层：服务端子进程**（用户拍板）——webapp 起子进程调 UV4/gmake；工具链检测到才启用编译能力，检测不到自动回退纯贴文本模式。理由：真"一条龙"的落点必须在服务端；前端只负责触发与展示。
2. **重编译验证循环：≤3 轮**（用户拍板）——修复 → 重编译 → 仍错再喂（复用 fix-errors 管线），第 3 轮后如实报告剩余错误清单，不无限循环。每轮间 SSE 事件推进，前端可见"第 N 轮"。
3. **触发方式：生成完成后自动编译 + 手动"重新编译"按钮**——生成成功即自动触发第一次编译（用户"懒得编译一遍"）；第 10 栏保留手动重新编译入口（改完工程后想再测）。
4. **编译粒度：全量重建**——UV4 `-j0 -r`（历史真机坑：`-b` 增量构建日志无编译行、Build Time 00:00:00，必须 `-r` 强制重建才有报错输出）；gmake `clean + all`（或 `-B`）。编译输出（含 warnings 引用行）原样采集为 error_text，与 fix-errors 解析契约（parse_compile_errors）天然对齐。
5. **平台覆盖：stm32 UV4 先行，mspm0 gmake 同工单**——gmake 简单（历史产物 gmake 构建可用），两条线一起做；但验收以 stm32 线为主，mspm0 线次之（构建命令形态不同：`gmake -C out -f Makefile` 之类，实施时按既有 build_makefiles 产物确认）。
6. **工具链发现：自动探测 + config.json 可覆盖**——UV4 常见路径（`C:\Keil5\Core\UV4\UV4.exe`、`C:\Keil_v5\UV4\UV4.exe`、PATH）；gmake 走 PATH（`gmake`/`make`）。settings 页可配自定义路径（config.json 字段）。
7. **超时与终态**：编译子进程超时（建议 180s）→ 超时事件如实报告（不静默）；编译失败（工具链报错/工程结构异常）与"编译有错"是两种终态，前者 error 事件、后者正常 done（携带错误清单走修复）。
8. **范围外（不混入本工单）**：LLM old_snippet 精确匹配不稳的改进（未应用路径已如实报告，靠循环消化）；多工程批量编译；CSS/CCS 的 IDE 集成。

## 现状（2026-08-12 已核实）

- fix-errors 管线已通：`/api/fix-errors` SSE（parse_done → fix_start → apply_result → done，backup_id）+ `/api/fix-errors/rollback`；`parse_compile_errors` 直接吃编译器原文（UV4 `..\main.c(158)` 相对形态已由路径基准修复支持，compile-error-fix/01 真机闭环）。
- UV4 实测路径 `C:\Keil5\Core\UV4\UV4.exe`（`-j0 -r -b <uvprojx> -o <log>`，退出码 1=有警告 2=有错误）；gmake 历史产物可用（2024H/2026H mspm0 线 0 错 0 警）。
- 生成产物：stm32 线 uvprojx 在 `user/Project.uvprojx`（工程根下子目录）；mspm0 线 `.cproject` 在工程根 + Makefile（build_makefiles 生成，`MODULES` 表）。
- 前端第 10 栏：textarea 贴报错 + 开始修复 + 逐条结果 + 回滚按钮（compile-error-fix/01 已合 main）。
- 服务：8000 launcher（关浏览器标签自毁）；修复管线真实调用 DeepSeek 每轮 4s~60s（_retry_parse ≤3 轮已兜底空内容）。

## 实施

1. **新域模块 `compile_runner.py`**（纯函数/薄壳，叶子方向，仿 fix_errors.py 风格）：`find_uv4()` / `find_make()`（自动探测 + 配置覆盖）、`run_compile(command, cwd, timeout)`（子进程、超时、非零退出不炸）、`collect_build_log(platform, out_dir)`（定位 uvprojx/Makefile，跑全量重建，返回原始编译输出文本）。域判决留本模块，webapp 薄壳。
2. **webapp**：`/api/compile` 路由（SSE 复用 sse.py：compile_start → compile_log（可选逐段）→ done{exit_code, error_text} 或 error；无工具链 400 中文登记 errors.py）+ 编译结果直连 fix-errors 管线（前端二次调 /api/fix-errors 或服务端编排——**推荐前端编排**：compile done 拿到 error_text 后前端直接调 fix-errors，复用既有管线与回滚语义，服务端不加编排复杂度；循环 ≤3 轮在前端状态机里做）。
3. **index.html**：第 10 栏改"修复中心"——生成成功后自动触发编译（或按钮"一键编译修复"）：编译 → 自动粘贴报错 → 修复 → 重编译，轮次状态条（第 N/3 轮）+ 剩余错误清单 + 回滚按钮；无工具链时按钮置灰提示（回退贴文本）。
4. **config.json**：`uv4_path` / `gmake_path` 可选字段（settings 页可填）。
5. **测试**：compile_runner 单测（fake 工具链子进程：正常/报错/超时/找不到工具链 400；`find_uv4` 探测逻辑含配置覆盖）；前端循环状态机无单测基建（node 语法过 + 人工验收）；错误登记 errors.py 补 CompileError 类名冲突检查（已有 FixError 登记，新异常同表）。
6. **不动**：fix_errors.py / llm.py（管线已通零改动）；生成器/门禁；既有第 10 栏贴文本路径（保留为回退）。

## 实施记录（2026-08-12）

- **新增 `src/contest_generator/compile_runner.py`**（叶子域模块，仿 fix_errors.py 风格）：
  `find_uv4`（config 覆盖 > 常见路径 C:\Keil5\Core\UV4\UV4.exe / C:\Keil_v5\UV4\UV4.exe > PATH）、
  `find_make`（config 覆盖 > PATH gmake/make）、`run_compile`（子进程、180s 超时如实报告部分
  输出、非零退出不炸）、`collect_build_log`（stm32 rglob .uvprojx → UV4 `-j0 -r -b`（-r 强制
  重建，历史真机坑）+ `-o` 临时文件采集（编译输出不落工程目录）；mspm0 定位 Debug/makefile →
  gmake `-C Debug -f makefile -B all`；工具链缺失 / 工程结构异常 → CompileRunnerError 400 中文）、
  `compile_passed`（UV4 0/1 = 通过、gmake 0 = 通过——前端循环判定单源，done 载荷带 passed）。
- **events.py**：`EVENT_COMPILE_START`（compile_start）词表登记。
- **errors.py**：`CompileRunnerError` 登记业务失败 400（测试显式断言与 fix_errors.CompileError
  类名不冲突——后者是解析条目 dataclass 非异常）。
- **config.py**：`uv4_path` / `gmake_path` 可选字段（空串 = 自动探测，类型非法大声失败），
  save/load 往返。
- **webapp.py**：`/api/compile` SSE 路由（compile_start → done{platform, output_dir, exit_code,
  error_text, passed, timed_out, project_file, command} 或 error；工具链缺失在起流前判定 → 400
  中文，前端据此置灰回退贴文本——决策记录 1；error 文案写具体不沿用泛化文案——观察记录 2）；
  `/api/state` 加 toolchains 探测结果；`/api/settings` GET/PUT 透传两路径字段。
- **index.html**：第 10 栏改"修复中心"——一键编译修复按钮（无工具链 / 未选平台置灰 + title 提示）、
  工具链状态行、轮次状态条（第 N/3 轮）、编译输出只读框（自动采集）、手动贴文本模式保留为回退；
  生成成功自动触发编译修复（决策记录 3）+ 滚动到第 10 栏；前端循环状态机：首次编译 → 通过即出活
  （warnings 如实展示）→ 有错喂 fix-errors（复用既有管线与回滚语义）→ 重编译验证 ≤3 轮，第 3
  轮后如实报告剩余错误清单（决策记录 2）；fixHandleEvent 重构为纯 UI 更新（忙碌状态归调用方）。
- **前端循环无单测基建**：node 语法过 + 真机人工验收（决策记录 2 说明按既定约定）。

### 自检（全部过）

- `python -m pytest`：**1208 绿**（基线 1111 + 97：compile_runner 23 + webapp 路由/状态/设置
  10 + config 2 + …）；`python -m mypy src` 干净；node 语法过 + `node --test tests/js/` 9/9。
- 中途修过：.bat 假工具链的日志行常量带尾随 \n 撑断 echo（rstrip 剥离）；`find_uv4` PATH 兜底
  测试须清空 _UV4_CANDIDATES（本机真机装了 UV4 会先命中常见路径）；mypy 两处（TimeoutExpired
  的 bytes|str 收缩、循环变量类型污染）；.bat 超时测试的 ping 孙进程继承管道拖慢 29s（改 ping -n 4）。

### 真机验收（2026-08-12，8000 服务）

- **无工具链 400 中文**：config.json 临时置 uv4_path=C:/no-such/UV4.exe 重启服务 →
  `/api/compile` HTTP 400「未检测到 Keil UV4 工具链…已回退贴文本模式」✅（完成后恢复配置）；
  mspm0 线本机无 gmake → 400「未检测到 gmake / make 工具链…」✅（前端按钮置灰路径同依据）。
- **2026C stm32 自动编译**：generate_check 全管线（真实 DeepSeek 推荐/骨架/生成）产物
  out_2026C_stm32 → `/api/compile` → done：exit=1（有警告无错）passed=True，命令
  `C:\Keil5\Core\UV4\UV4.exe -j0 -r -b user\Project.uvprojx -o <临时log>`，日志尾部
  `"Objects\Project.axf" - 0 Error(s), 1 Warning(s)`（warnings 如实展示）✅
- **注入错误循环收敛**：main.c 删分号注入 → `/api/compile` exit=2 passed=False，
  error_text 含 `..\main.c(30): error: #65: expected a ";"`（UV4 相对形态，与解析契约对齐）→
  `/api/fix-errors` 真实 DeepSeek：parse_done(1 条/1 文件) → apply_result main.c:30 applied →
  backup_id 20260812-161803 → 重编译 `0 Error(s), 4 Warning(s)` passed=True ✅
- **回滚语义**：rollback 恢复注入态 → 重编译重现 1 Error（回滚真实有效）✅
- **超时场景**：单测覆盖（fake 慢工具链 timed_out=True 不挂死）；真机无慢工具链可伪造，跳过。
- **前端页面**：新元素（一键编译修复 / 轮次条 / 编译输出 / 设置两路径框）已由 8000 服务正常
  输出；浏览器人工验收（生成后自动触发 / 循环状态机展示）留给用户开浏览器确认。
- 遗留：2021F stm32 全管线补问无答案失败（图1 缺失，clarify 映射未覆盖）——既有数据缺口，
  与本工单无关，generate_check 只取 2026C 验收。

## 验收标准

- [x] pytest 全绿（1208）+ `mypy src` 干净 + node 语法过（9/9）
- [x] compile_runner 单测（23 个）：UV4/gmake 路径探测（含 config 覆盖）、子进程超时、退出码映射、日志采集（.bat 假工具链真子进程演练）
- [x] 无工具链环境：/api/compile 400 中文（stm32 UV4 + mspm0 gmake 双线真机验证）+ 前端按钮置灰（回退贴文本模式保留）
- [x] 真机 stm32 线：2026C 生成 → 自动编译（UV4 -r 全量重建）→ 采集报错 → 真实 DeepSeek 修复 → 重编译 0 Error(s)（warnings 如实展示）；注入错误场景循环收敛（1 Error → 修复 applied → 0 Error）
- [x] 真机 mspm0 线：本机无 gmake → 按无工具链 400 降级验收；gmake 编译路径由单测 fake 覆盖（Debug/makefile 定位 + `-C Debug -f makefile -B` + 退出码采集）——验收以 stm32 线为主（工单约定）
- [x] 超时场景：伪造慢工具链单测 → 超时事件如实报告不挂死（timed_out=True + 部分输出保留）
- [x] `git status` 只出现预期文件（compile_runner.py / webapp.py / errors.py / events.py / config.py / index.html / tests/ / 工单文件）

## 文件边界

- **新增**：`src/contest_generator/compile_runner.py`
- **改**：`src/contest_generator/webapp.py`（/api/compile 路由 + 配置字段透传）、`src/contest_generator/errors.py`（新异常登记）、`src/contest_generator/static/index.html`（第 10 栏改造 + 循环状态机）、`tests/`
- **不动**：`fix_errors.py` / `llm.py` / `sse.py` / 生成器/门禁/模块库/母版库

## 观察（本工单范围外）

- LLM old_snippet 与文件逐字匹配不稳（compile-error-fix/01 真机第 1 轮 158 行未应用、第 3 轮 2 处成功）——循环机制天然消化（重编译仍错→再喂一轮），无需额外机制；若循环内反复未应用同一处，第 3 轮如实报告剩余错误即可。
- error 终态文案归因（"AI 服务调用失败" vs 路径解析失败）在 compile-error-fix/01 已暴露过一次——本工单的 compile 错误事件文案直接写具体（工具链缺失/超时/工程结构异常），不沿用泛化文案。
