# 01 — 修复循环纳入 warning：0 错 N 警即停，违背「0 错 0 警」验收标准

**What to build:** 修复循环把 warning 纳入收敛目标——现状 0 Error + N Warning 即宣告「编译通过」，警告只展示不修（前端「warnings 见上方编译输出」/ CLI 摘要行连警数都不打）。机械链路已全通（parse_compile_errors 已解析 warning 行、/api/compile 已回 summary、回喂走完整编译输出），唯一缺口是**触发条件**：修触发与停条件只看 errors。真机 2026C 曾 0 错 4 警（骨架占位声明，skeleton-no-unused-vars/01 已从提示词侧压制）——概率性压制 + 确定性兜底才算闭环。

**Status:** 待实施（实施提示词见文末）

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

- [ ] 红证：契约测试先行跑红（FIX_SYSTEM_PROMPT 无 warning 指引词）
- [ ] 实施后：契约绿 + CLI 结构钉绿 + 既有全绿 + `mypy src` 干净 + `node --check` 过
- [ ] 真机：2026C --reuse-recommend 正常管线 0 错 0 警（回归不破）；**注警形态**：main.c 注入未用变量 → 旧行为先采红证（停在 1 警）→ 实施后 CLI 自动续跑告警轮 → UV4 0 Error(s) 0 Warning(s)（若 LLM 不修 → 提示词措辞回炉，本工单不关）
- [ ] （可选）前端浏览器人工：注入未用变量 → 一键编译修复 → 自动清零到「0 错 0 警」终态
- [ ] `git status` 只出现预期文件

## 实施提示词（新会话粘贴）

> 工单：`.scratch/fix-loop-warnings/issues/01-warning-convergence.md`（先读全文）。
> 任务：修复循环纳入 warning 收敛（前端 + CLI 对偶 + FIX_SYSTEM_PROMPT 指引），红证先行，真机注警验证。
> 文件边界：只动 `src/contest_generator/llm.py` + `src/contest_generator/static/index.html` + `.scratch/real-run/generate_check.py` + `tests/test_llm.py` + `tests/test_generate_check_contract.py`；`webapp.py` / `fix_errors.py` / `generator.py` 零改动。
> 关键：停条件 `passed` → `passed && warnings === 0`（前端两处 + CLI 两处）；FIX_MAX_ROUNDS 仍 3 不动（契约测试双文本钉在）；CLI 摘要行补警数 + 0-applied 即停同步（docstring 已预告一行之差）；parse/summary 单源已就绪，别另写正则。
> 真机验收：服务 8000 → 2026C --reuse-recommend 正常管线 0/0 回归；注警红证先采（main.c 注入 `int unused_probe = 1;` → 旧行为停在 1 警）→ 实施后自动续跑告警轮 UV4 0 Error(s) 0 Warning(s)；证据写 Comments，Status 改 resolved，docs 提交推送。

## Comments
