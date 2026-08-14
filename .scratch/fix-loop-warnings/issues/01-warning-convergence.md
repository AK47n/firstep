# 01 — 修复循环纳入 warning：0 错 N 警即停，违背「0 错 0 警」验收标准

**What to build:** 修复循环把 warning 纳入收敛目标——现状 0 Error + N Warning 即宣告「编译通过」，警告只展示不修（前端「warnings 见上方编译输出」/ CLI 摘要行连警数都不打）。机械链路已全通（parse_compile_errors 已解析 warning 行、/api/compile 已回 summary、回喂走完整编译输出），唯一缺口是**触发条件**：修触发与停条件只看 errors。真机 2026C 曾 0 错 4 警（骨架占位声明，skeleton-no-unused-vars/01 已从提示词侧压制）——概率性压制 + 确定性兜底才算闭环。

**Status:** resolved（2026-08-14 实施 + 真机注警验收闭环——0 错 0 警停条件双端落地，真机注入 #177-D 告警自动续跑修复轮 UV4 0 Error(s) 0 Warning(s)）

## 现状证据（2026-08-14 读码核实）

- **解析端已通**：`fix_errors.parse_compile_errors` 双形态正则都匹配 warning 行（既有测试 test_parse_uv4_warning_and_column）；`summarize_compile_output` 已回 {errors, warnings}——后端零改动是本工单前提。
- **数据端已通**：webapp /api/compile done 载荷已含 summary（{errors, warnings}，compile-experience-ui/01）。
- **前端触发缺口**（index.html startFixCenter）：首编 `initial.passed` → 直接「编译通过 ✅（warnings 见上方编译输出）」返回；轮内 `compile.passed` → 「重编译通过 ✅（warnings 见上方编译输出）」返回——0 错即停，警告永不进修复轮。
- **CLI 触发缺口**（.scratch/real-run/generate_check.py）：check_topic 首编 `passed` → `[真机] ✓ {summary}` 收工；run_fix_loop 轮内 `if passed: return True` 同停。uv4_build/gmake_build 摘要行只有「{errors} 错误」，warning 数不可见。
- **提示词缺口**：FIX_SYSTEM_PROMPT 只说「逐条修复报错」，无 warning 修复指引（删未用声明 / 补引用 vs 模块自带警不瞎改）。
- **红证形态（可复现）**：向生成产物 main.c 注入一行全局未用变量 `int unused_probe = 1;` → UV4 0 Error 1 Warning（#177-D，exit=0 → passed=True）→ 现状循环直接停，警残留。修复链路本可兜底（warning 行喂进去 LLM 就能删声明），但没有触发。

## 修复方向（三件套，实施会话定措辞，红证先行）

1. **FIX_SYSTEM_PROMPT 补 warning 修复指引**（约束 7，llm.py）：编译输出中的 warning 条目同样修复——未使用变量/函数（删除声明或补引用）、告警指出的实质问题照修；第三方库 / 模块自带警告（宏重定义等）不瞎改，依据不足照约束 5 宁可不输出。契约测试 test_llm.py 断言指引词在场（红证：现行提示词无此词）。
2. **前端循环纳入 warning**（index.html）：停条件 `passed` → `passed && warnings === 0`；首编 passed 但有警 → 同样进循环（告警轮，errorText = 完整编译输出，warning 行自然进修复）；轮次文案补「N 条 Warning」形态；终态区分「0 错 0 警 ✅」/「仍剩 N 警」。0-applied 即停已存在（告警轮无建议自然停，文案补具体）。FIX_MAX_ROUNDS 仍 3（错误+告警共池），契约测试双文本钉不动。
3. **CLI 对偶**（.scratch/real-run/generate_check.py）：摘要行补 warning 数（「{errors} 错误 {warnings} 警」，uv4_build/gmake_build 两处）；check_topic 首编 passed 有警 → 进 run_fix_loop；run_fix_loop 停条件 `passed and warnings == 0`；顺手同步 T2 的 0-applied 即停（docstring 已预告「一行之差」——告警轮无建议不再空转 3 轮）。结构钉照 FIX_MAX_ROUNDS 双文本钉先例（test_generate_check_contract.py：run_fix_loop 停条件引用 warnings 判定 + 摘要行含警数）。

## 实施边界

- src：`src/contest_generator/llm.py`（FIX_SYSTEM_PROMPT 约束 7）+ `src/contest_generator/static/index.html`（循环条件与文案）。
- scratch 工具：`.scratch/real-run/generate_check.py`（CLI 对偶三处）。
- tests：`tests/test_llm.py`（契约测试）+ `tests/test_generate_check_contract.py`（CLI 结构钉）+ node --check index.html。
- 零改动：`webapp.py` / `fix_errors.py` / `generator.py` / `makefiles.py`（parse/summary 单源已就绪）。

## 验收标准

- [x] 红证：契约测试先行跑红（FIX_SYSTEM_PROMPT 无 warning 指引词）
- [x] 实施后：契约绿 + CLI 结构钉绿 + 既有全绿 + `mypy src` 干净 + `node --check` 过
- [x] 真机：2026C --reuse-recommend 正常管线 0 错 0 警（回归不破）；**注警形态**：main.c 注入未用变量 → 旧行为先采红证（停在 1 警）→ 实施后 CLI 自动续跑告警轮 → UV4 0 Error(s) 0 Warning(s)（若 LLM 不修 → 提示词措辞回炉，本工单不关）
- [ ] （可选）前端浏览器人工：注入未用变量 → 一键编译修复 → 自动清零到「0 错 0 警」终态
- [x] `git status` 只出现预期文件

## 实施提示词（新会话粘贴）

> 工单：`.scratch/fix-loop-warnings/issues/01-warning-convergence.md`（先读全文）。
> 任务：修复循环纳入 warning 收敛（前端 + CLI 对偶 + FIX_SYSTEM_PROMPT 指引），红证先行，真机注警验证。
> 文件边界：只动 `src/contest_generator/llm.py` + `src/contest_generator/static/index.html` + `.scratch/real-run/generate_check.py` + `tests/test_llm.py` + `tests/test_generate_check_contract.py`；`webapp.py` / `fix_errors.py` / `generator.py` 零改动。
> 关键：停条件 `passed` → `passed && warnings === 0`（前端两处 + CLI 两处）；FIX_MAX_ROUNDS 仍 3 不动（契约测试双文本钉在）；CLI 摘要行补警数 + 0-applied 即停同步（docstring 已预告一行之差）；parse/summary 单源已就绪，别另写正则。
> 真机验收：服务 8000 → 2026C --reuse-recommend 正常管线 0/0 回归；注警红证先采（main.c 注入 `int unused_probe = 1;` → 旧行为停在 1 警）→ 实施后自动续跑告警轮 UV4 0 Error(s) 0 Warning(s)；证据写 Comments，Status 改 resolved，docs 提交推送。

## Comments

### 2026-08-14 实施 + 真机验收闭环（Status resolved）

**红证（契约，先行跑红）4 条**：`test_fix_system_prompt_warning_guidance`（llm.py 无「Warning / 未使用变量 / 不瞎改」指引词）+ CLI 结构钉 3 条（run_fix_loop 停条件未引 warnings、check_topic passed 分支未引 warnings、uv4/gmake 摘要行无警数）——实施前全红。

**真机红证（旧代码）**：注入形态**修正**——立单写的「全局未用变量」真机实测 ARMCC 不报警（全局可被外部引用，0/0 复编确认），改注入 main() 内**局部**变量 `int unused_probe = 1;`（与骨架 4 警同款 #177-D 形态）。旧行为证据：`UV4 exit=1 … 0 Error(s), 1 Warning(s)`（`..\main.c(23): warning: #177-D: variable "unused_probe" was declared but never referenced`）→ `compile_passed` = True → 旧 check_topic `[真机] ✓ UV4 exit=1 …（0 错误）` 直接收工（警数不可见、告警轮未触发、注入行残留）。

**实施（三件套）**：
1. `llm.py` FIX_SYSTEM_PROMPT 约束 7：Warning 条目同样逐条修复（未使用变量/函数删声明或补引用、实质问题照修；第三方/模块自带警告如宏重定义不瞎改，依据不足同约束 5 宁可不输出）。预算注释同步：系统提示词 ≈3.3→3.8KB，最坏形态总量 120128 ≤ 120832（余量 704B，契约测试钉死仍绿）。
2. `index.html`：停条件两处 `passed → passed && warnings === 0`（首编 0 错 0 警才「编译通过 ✅ 0 错 0 警」收工；轮内重编译 0/0 才出活）；首编有警进告警轮（errorText = 完整编译输出，warning 行自然回喂）；轮次文案「编译有错（N 条 Error / M 条 Warning）」「编译有警（M 条 Warning）」双形态；0-applied 告警轮文案带剩余警数；3 轮上限终态区分「N 条 Error / M 条 Warning」。
3. `generate_check.py`：摘要行补警数（uv4_build / gmake_build 两处「{errors} 错误 {warnings} 警」）；check_topic 首编 passed 有警 → `[真机] 有 N 条 Warning，进入修复循环`；run_fix_loop 停条件 `passed and warnings == 0`（有警续跑告警轮）+ 0-applied 即停（docstring 预告的「一行之差」已同步）。FIX_MAX_ROUNDS 仍 3（契约测试双文本钉不动）。

**验证**：1366 绿（基线 1362 + 新 4 条）+ `mypy src` 37 文件干净 + `node --check` 内联 JS（95570 字符）过 + `git status` 只 5 预期文件。

**真机验收（新代码）**：
- 正常管线回归：`python generate_check.py 2026C --reuse-recommend` → `[真机] ✓ UV4 exit=0 Build Time Elapsed: 00:00:01（0 错误 0 警）`，汇总 `2026C: ✓ 通过`（第 1 次 400 = 旧 out 目录未清（已知坑）、第 2 次 502 = DeepSeek 上游瞬断 Remote end closed，第 3 次通过）。
- 注警形态（probe 脚本 `.scratch/real-run/warn_probe_new.py`，逐行复刻新 check_topic 尾部——check_topic 重生成会抹注入，probe 复用同源模块函数是唯一诚实路径）：
  ```
  已注入（main() 内局部变量）：int unused_probe = 1;
    [真机] ✓ UV4 exit=1 Build Time Elapsed:  00:00:01（0 错误 1 警）
    [真机] 有 1 条 Warning，进入修复循环（≤3 轮：告警 → AI 修复 → 重编译）
    第 1/3 轮：1 条 Warning → AI 修复…
    应用 1 处 / 跳过 0 处
      ✓ main.c:22 [applied]
    第 1 轮重编译 ✓ UV4 exit=0 Build Time Elapsed:  00:00:02（0 错误 0 警）
  [终检] UV4 exit=0 Build Time Elapsed:  00:00:01（0 错误 0 警）
  [终检] 注入行已除: True
  ```
  LLM 第 1 轮即删未用声明（约束 7 生效），提示词无需回炉。红证 probe 脚本 `warn_probe_old.py` 同目录留档。

**遗留**：（可选）前端浏览器人工验收未做（CLI 对偶链路已真机闭环）；旧 out 目录 400 与 DeepSeek 瞬断均为环境性，非本工单改动。
