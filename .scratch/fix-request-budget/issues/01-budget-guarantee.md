# 01 — 修复请求体预算保证：最坏情况文件上下文可 2× 撑爆 128KB，修复循环最后防线断

**What to build:** 修复请求（FIX_SYSTEM_PROMPT + `_fix_errors_user_prompt`）没有结构预算保证——recommend-speedup/01 D 棱镜给 select/clarify 补了「最坏情况 < MAX_REQUEST_BYTES 结构测试 + 预算反推」，fix 没有。文件上下文合计 49152 **字符**（`fix_errors.py:73`），按真实预检口径（`json.dumps` ensure_ascii=True，中文 6 字节/字符）最坏 ≈295KB 单段已超 128KB 总量 2 倍+——与 D 棱镜 60000-char cap 同款「预算数学自相矛盾」，且比那里更狠（那里按 3B/字符估，这里真实口径是 6B/字符）。

**Status:** 待实施（实施提示词见文末）

## 现状证据（2026-08-14 读码核实）

- **预检口径**：`_chat`（`llm.py:1324-1336`）`json.dumps(payload).encode("utf-8")` > MAX_REQUEST_BYTES 即抛 LLMError「请求体过大」——中文走 `\uXXXX` 转义 **6 字节/字符**，不是 UTF-8 的 3 字节。
- **修复用户提示词段**（`llm.py:1612-1668`）：报错全文 4000 字符（`_truncate_content`）、文件上下文合计 49152 字符（`FIX_CONTEXT_TOTAL_CHARS`，`read_file_contexts` 截断后**原样嵌入不再截断**）、dropped 清单无上限、previous_fixes 无上限、赛题 4000、main.c 4000。
- **最坏形态**：49152 字符中文注释 C 文件（库内模块普遍带中文注释，xunji control.c 等）→ 6B/字符 ≈ **295KB 单段**；纯 ASCII C 也有 48KB。加报错 24KB + 赛题 24KB + main.c 24KB（中文最坏）→ 必然超。
- **为什么真机没爆**：T3/注错场景命中的文件都小且近 ASCII（main.c 数 KB），纯属侥幸余量。
- **失败形态**：LLMError 无 kind（缺省 parse 类）→ `_retry_parse` 3 次快重试同尺寸必败 → error 事件「请求体过大」→ 前端循环停——**修复中心是最后防线，断了用户只能手工改**。
- **对照**：select/clarify 有结构测试钉死（`tests/test_llm.py:3207/3235`），但注意其口径是 `prompt.encode("utf-8")`（3B/字符），与真实预检 `json.dumps`（6B/字符）存在 2× 差——**fix 工单结构测试必须对齐真实预检口径，别继承这个差**。

## 修复方向（实施会话定参，红证先行）

1. **结构测试钉死**：`test_fix_prompt_worst_case_fits_request_budget`——文件上下文 = 预算上限形态 + 报错全文 4000 + 赛题实测形态（2026C 2626 字符）+ main.c 4000 + previous_fixes 上限形态 → **`json.dumps` 序列化** < MAX_REQUEST_BYTES（对齐 `llm.py:1329` 真实口径）；cap 改大即红。
2. **预算反推**：基础段（报错/赛题/main.c/回喂/系统提示词 1759B/JSON 壳）按各自内容形态估字节，余量给文件上下文——`FIX_CONTEXT_TOTAL_CHARS` 从 49152 反推下调，或改「wire 字节」记账口径（`read_file_contexts` 按字节扣预算）。**目标余量 ≥10KB**（D 棱镜余量 4602 太薄，且修复路径还有无上限的 previous_fixes 段）。
3. **previous_fixes 段级截断**（同 CLARIFICATION_HISTORY_CAP=2500 哲学）：段级合计上限（建议 ~2000-2500 字符）+ 截头标注；逐条 reason 是固定文案本已有界，防的是 LLM 返回海量 fixes 时 N×150 字符无界增长。
4. **dropped 清单**：短路径拼接，最坏数百条也 KB 级——结构测试覆盖即可，不强加上限。

## 实施边界

- src：`src/contest_generator/fix_errors.py`（预算常量/记账口径）+ `src/contest_generator/llm.py`（previous_fixes 段截断 + 预算推导注释）。`generator.py` / `webapp.py` / `index.html` 零改动。
- tests：`tests/test_fix_errors.py`（预算记账用例）+ `tests/test_llm.py`（结构测试 + previous_fixes 截断断言）。红证先写：现行 49152 cap 跑红 → 调参后绿。
- 不动：compile_runner / 修复协议 / 事件词表 / 前端。

## 验收标准

- [ ] 红证：结构测试在现行 49152 cap 下跑红（> MAX_REQUEST_BYTES）
- [ ] 修复后：结构测试绿（json.dumps 口径，余量 ≥10KB）+ cap 改大即红
- [ ] 既有测试全绿 + `mypy src` 干净
- [ ] （可选）真机 HTTP 层：合成超大中文文件上下文的 /api/fix-errors 请求 → 不再「请求体过大」，修复轮正常返回
- [ ] `git status` 只出现预期文件

## 实施提示词（新会话粘贴）

> 工单：`.scratch/fix-request-budget/issues/01-budget-guarantee.md`（先读全文）。
> 任务：给修复请求补结构预算保证（同 recommend-speedup/01 D 棱镜），红证先行。
> 文件边界：只动 `src/contest_generator/fix_errors.py` + `src/contest_generator/llm.py` + `tests/test_fix_errors.py` + `tests/test_llm.py`；`generator.py` / `webapp.py` / `index.html` 零改动。
> 关键：结构测试必须用 `json.dumps` 序列化口径（对齐 `llm.py:1329` 真实预检，中文 6B/字符）——别继承 select 测试的 `prompt.encode` 3B 口径；余量目标 ≥10KB。
> 验收：红证（现行 49152 cap 跑红）→ 调参绿 + cap 改大即红 + 既有全绿 + `mypy src` 干净；证据写 Comments，Status 改 resolved，docs 提交推送。

## Comments
