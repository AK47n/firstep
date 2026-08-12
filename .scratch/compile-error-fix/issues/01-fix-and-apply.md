# 01 — 编译错误回填自愈（贴报错 → LLM 修复 → 直接写回工程）

**What to build:** 生成页新增第 10 栏「编译错误修复」：用户把 Keil/CCS 编译报错文本贴回工具 → 工具解析文件引用、从生成输出目录读真实文件内容、连同题面/平台/模块/main.c 上下文交给 LLM 逐条修复 → **直接写回工程文件**（备份 + 可回滚）。闭环"生成 → 编译 → 报错 → 修复"。

**Status:** resolved（2026-08-12 实施完成：1172 绿 + mypy 干净 + node 语法过；真机验收闭环 2026-08-12：全链路实测通过 + 路径基准 blocker 修复（本工单后续 commit））

## 真机验收记录（2026-08-12，接口层全真实链路，用户授权执行）

**链路**：真实生成（/api/generate 直连 2026C stm32，5 模块 out_fix_accept）→ 注入编译错误 + 发现历史真实错误 → 真实 UV4 编译（/c/Keil5/Core/UV4/UV4.exe -j0 -r -b）→ 真实 DeepSeek 修复（三轮）→ 写回验证 → 回滚验证 → 最终重编译 **0 Error(s) 4 Warning(s)**。

**验收发现 blocker（已修复）**：stm32 母版产物 uvprojx 在 `user/` 子目录，UV4 报错路径是相对它的 `..\main.c(158)` 形态——`collect_candidate_paths` 用 `is_unsafe_path` 拒 `..` 且 containment 以工程根为基准 → **真实布局下候选全空（file_count=0）→ 全降级 → LLM 建议被空 file 清单拒绝 → 3 轮重试 × ~65s 真实调用白跑 → error 终态"AI 服务调用失败"（误导归因）**。单测 UV4 用例用无前缀形态，与真实输出脱节。

**修复（域内方案）**：`fix_errors.py` 新增 `_report_benchmarks`（rglob 探测 `.uvprojx`/`.cproject` 父目录）+ `collect_candidate_paths` 双基准解析（先工程根，再工程文件基准，containment 兜底安全——`..` 逃逸/绝对路径自然越界被拒）+ `_resolve_in_root`。红证：新增 3 用例（UV4 `..\` 形态 → 候选 main.c；`..` 逃逸仍拒；CCS 相对形态不受影响）。**pytest 1175 全绿（基线 1172 + 3）+ mypy 干净**。

**三轮修复实录**（真实 DeepSeek，每轮 4s~57s）：
- 第 1 轮（2 errors：TAGID_MASK 80 行 + 注入 UNDECLARED_SYMBOL_ZZZ 158 行）：file_count=1（main.c，`..\` 归一生效）；80 行 **applied**（LLM 把 `id & TAGID_MASK` 修成 `id & 0x0F`）、158 行 **skipped 如实报告**（old_snippet 不匹配，协议内行为）；backup_id=20260812-154628；重编译 2 errors→1 error。
- 回滚验证：`restored: ["main.c"]`，TAGID_MASK 行恢复原样 ✓（回滚后第二轮只修报错对应的 zzz 行，行为链正确）。
- 第 2 轮（仅 158 行）：**applied** ✓（未应用 → 再贴 → 修完的循环成立）。
- 第 3 轮（仅 80 行，2 处 applied）→ 最终重编译 **0 Error(s) 4 Warning(s)**（4 警 = LLM 骨架未用变量，历史固有非回归）。

**附带观察**：① 路径基准修复使服务端已具备"接受编译器原文报错"能力，为一条龙（自动编译采集报错）铺路；② LLM 的 old_snippet 与文件逐字匹配存在不稳定（第 1 轮 158 行失败、第 3 轮 2 处成功），未应用路径真实常见且如实报告——用户体验上靠"再贴一轮"或后续自动循环消化；③ 8000 launcher 服务会因关浏览器标签自毁（tabs/bye → os._exit），验收中需自起服务。

## 决策记录（grilling 2026-08-12，与用户确认）

1. **写回形态：直接写回，不要预览确认**（用户拍板 B）——理由：生成工程可再生 + 自动备份可回滚，双重保险，无需打断用户流
2. **可逆性**：写回前把本次要改的文件原内容备份（存输出目录外，如 `~/.contest_generator/fix-backups/<timestamp>/`），UI 提供「回滚本次修复」按钮
3. **可写白名单**：仅 `.c/.h/.s`（大写 `.S` 可考虑）；路径必须 resolve 后仍在输出目录内（复用 `is_unsafe_path` 原语防穿越）；其他文件类型拒绝
4. **替换协议**：LLM 返回 `{file, line, old_snippet, new_snippet, reason}` 列表；工具在文件内精确匹配 `old_snippet` 后替换；**匹配失败该处跳过并报告"未应用"**（不静默、不模糊替换）；一处 snippet 在文件内出现多次时要求 LLM 给足够上下文片段消歧，仍歧义则该处跳过
5. **报错解析**：正则提取 `文件(行号):` 与 `文件:行号:` 两种形态（UV4 如 `..\out\code\main.c(123): error #20: ...`，CCS 如 `code/sub/mod.c:45: error: ...`），解析出相对路径 + 行号；按输出目录（生成结果 res-dir）解析真实路径；解析不到文件引用或读取失败 → 降级：整段错误文本 + 无文件上下文给 LLM（仍可修，只是不精准）
6. **上下文注入**：报错命中的文件内容（截断到合理上限，如每文件 500 行/50KB）+ 题面 + 平台 + 模块清单 + main.c + 错误全文
7. **LLM**：新函数（llm.py 机械层，如 `fix_compile_errors`），fake 支持；输出走 JSON 结构化解析（复用 `_retry_parse` 重试兜底 ≤3 轮）
8. **流式**：SSE 复用现有 sse.py 模式（解析中 → 修复中 → 每处应用结果 → 完成）
9. **范围外（后续增强，另立工单）**：修复后自动重编译验证（UV4 -b / gmake，环境检测到才跑）——能力独立且大，不混入本工单
10. **不动既有结构**：webapp 只加路由薄壳 + 注册；模块库/母版库/门禁零改动

## 现状（2026-08-12 核查）

- 输出目录：生成结果 `res-dir` 已在前端展示（`$("res-dir")`），工具可得知工程位置
- 复用原语：`entry_store.is_unsafe_path`（穿越校验）、`sse.py`（SSE 流式）、`llm._retry_parse`（解析重试）、`errors.py`（业务错误登记 400）
- 用户真机验收环境：Keil UV4 命令行可用、gmake 可用（历史验收记录为证）——本工单不用，后续增强用
- 报错文本典型形态（真机验收记录里的 UV4 输出）确认过格式

## 验收标准

- [x] pytest 全绿 + `mypy src` 干净（2026-08-12：1172 通过（+61），`mypy src` Success 34 files，node --check 内联 JS 通过）
- [x] 报错解析单测：UV4 格式 / CCS 格式 / 混合多文件 / 无文件引用降级 / 垃圾文本不崩（test_fix_errors.py：UV4 带列号 / armclang `path:line:col:` 同 CCS 形 / 绝对形态降级）
- [x] 路径安全测试：`../` 逃逸、绝对路径、非法扩展名均拒绝（400 中文，登记 errors.py）（apply_fixes 9 例参数化 FixError + error_entry 400 断言 + 路由级：SSE error 终态中文 / 回滚非法 backup_id 400）
- [x] 替换应用测试：精确匹配成功 / 缩进不匹配跳过并报告 / 多处歧义跳过（含同文件多处修复顺序应用、无应用不备份）
- [x] 备份与回滚测试：写回前备份存在；回滚后文件内容恢复原样（备份镜像在输出目录外 `工作根/fix-backups/<ts>/`，回滚逐路径 containment 复检）
- [x] LLM fake 端到端：构造报错 → 文件被正确修改（路由级 test_fix_errors_end_to_end_fake_llm：双文件应用 + 回滚恢复原样）
- [x] 浏览器人工验收：生成一个工程 → 故意制造一个编译错误（或真实编译）→ 贴回 → 修复写回 → 文件内容确实变了 → 回滚按钮恢复（**待用户真机浏览器验收**；实施侧已覆盖：SSE 事件序列契约测试 + fake 端到端 + 上下文透传断言）
- [x] `git status` 只出现预期文件（新增 fix_errors.py / test_fix_errors.py，改 errors/events/llm/webapp/index.html/fakes/test_llm/test_webapp，边界内零越界）

## 实施记录（2026-08-12）

- **fix_errors.py（新增，域模块，纯函数）**：`parse_compile_errors`（UV4 `path(line[,col]):` 与 CCS/armclang `path:line[:col]: (fatal) error|warning` 双正则，路径归一 POSIX，反斜杠开头绝对形态降级）/ `collect_candidate_paths`（白名单 .c/.h/.s + `is_unsafe_path` + resolve containment + 存在性，去重保序）/ `read_file_contexts`（单文件 500 行 / 50KB 双上限带标注，总预算 48KB 超预算点名返回）/ `apply_fixes`（内存完成替换 → 备份全部改动文件 → 才写回；匹配失败 / 歧义跳过报告「未应用」；路径越界 FixError）/ `backup_files` + `restore_backup`（`工作根/fix-backups/<timestamp>/` 镜像，backup_id 与镜像内路径双重 is_unsafe_path 校验）+ `fix_backup_root`
- **llm.py**：`FIX_SYSTEM_PROMPT`（snippet 替换协议唯一表述：逐字一致 / 唯一匹配 / file 限清单）+ `fix_compile_errors`（Protocol + DeepSeekLLM，`_retry_parse` ≤3 轮，json_mode）+ `parse_fix_suggestions`（严格：file 限清单 / old_snippet 非空，畸形 LLMError 整次重问）+ `_fix_errors_user_prompt`（报错全文 + 文件内容 + 题面 / 平台 / 模块 / main.c，降级模式显式告知）；只做机械提取，域判决全部留 fix_errors.py
- **webapp.py**：`/api/fix-errors`（SSE：parse_done → fix_start → apply_result… → done，done 载荷带 backup_id / parsed / degraded / fixes；输出目录不存在 400）+ `/api/fix-errors/rollback`（同步：restore_backup，非法 backup_id 400）
- **events.py**：`parse_done` / `fix_start` / `apply_result` 词表 + ProgressEvent 字段（error_count / file / line / status / reason）
- **errors.py**：`FixError` 登记 → 400 中文（结构测试自动兜底）
- **index.html**：第 10 栏 UI（textarea 贴报错 + 开始修复 + 回滚按钮 + 逐条结果列表），SSE 消费复用 parseSSE；输出目录取 `res-dir` 优先、`output-dir` 兜底；断线守卫 / 上下文透传
- **不动**：模块库 / 母版库 / 门禁 / generator 装配 / 既有 9 栏零改动

## 文件边界（实施提示词）

- **新增**：`src/contest_generator/fix_errors.py`（域模块：报错解析 `parse_compile_errors` / 文件定位读取 / snippet 替换应用 `apply_fixes` / 备份 `backup_files`+`restore_backup`——全部纯函数可单测）
- **改**：`src/contest_generator/webapp.py`（新增 `/api/fix-errors` 路由，SSE 流式，薄壳收口调域模块；错误登记 errors.py）
- **改**：`src/contest_generator/llm.py`（新增机械提取函数 + 协议；域判决留在 fix_errors.py 或 selection 侧，按 llm 拆层既定方向）
- **改**：`src/contest_generator/static/index.html`（第 10 栏 UI：textarea 贴报错 + 修复按钮 + 逐条结果 + 回滚按钮；SSE 解析复用）
- **改**：`tests/`（对应单测 + fake 端到端）
- **不动**：模块库/母版库/门禁/generator 装配逻辑/现有 9 栏
