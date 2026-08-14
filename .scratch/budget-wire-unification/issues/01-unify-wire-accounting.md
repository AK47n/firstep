# 01 — 请求预算 wire 口径统一：推荐侧结构测试在测错误的序列化，全中文最坏形态实发 ≈250KB 必炸 128KB 网关

**What to build:** 请求预算记账单一出处 + 推荐侧（select/clarify）补 wire 字节记账。现状两套口径并行：修复侧 wire 字节精确记账（`_wire_size`/`_fit_wire_budget`，`fix_errors.py:352-376`，全中文结构测试钉死 119532≤120832）；推荐侧字符 cap + 3B/字符估算（`REFERENCE_FULLTEXT_CAP` 35000「×3 字节 ≈105KB ≤128KB 恒成立」`llm.py:302-309`）——但真实线格式是 `json.dumps(payload).encode("utf-8")` 且 ensure_ascii 默认开（`llm.py:1365`），中文实发 **6 字节/字符**。select 最坏形态结构测试（`tests/test_llm.py:3316`）拿全中文 fixture（`"中" * 35000`）断言 `prompt.encode("utf-8")`——3B 口径假绿，同一载荷真实线 ≈250KB，网关 413 → 网络类重试 3 连同尺寸必败 → LLMError。fix-request-budget/01 当时白纸黑字警告「select 结构测试 prompt.encode 3B 口径勿继承」——警告没被继承，风险留下。

**Status:** resolved

## 验收记录（2026-08-14，refactor 20b7ff4）

- **红证先行（只换结构测试口径、实现不动）**：select 最坏用例 `assert 256001 <= (131072 - 10240)` 红——同一载荷旧实现真实线 **256001 字节**，超 120832 上限 2.12×（3B 口径假绿实锤；clarify 用例换口径后仍绿 40728，无全文段）。
- **实施后结构测试**（json.dumps payload 口径，题面改 4000 推导最坏形态 + `"中" * REFERENCE_FULLTEXT_BYTES` 全文 fixture）：select 最坏总量 **120610 ≤ 120832**，余量 **10462 ≥ 10KB**；clarify 40728。测试绿 + `仅展示前 67000 wire 字节` 全文截断标注断言在场。
- **新常量改大即红**：`REFERENCE_FULLTEXT_BYTES` 临时改 71096（+4096）→ select 结构测试红 `assert 124582 <= 120832`；恢复 67000。
- **fix 侧零回归**：`test_fix_prompt_worst_case_fits_request_budget` 及 test_fix_errors.py 预算用例逐字节断言零改动（仅 `_fit_wire_budget/_wire_size` import 面迁 budget 一处跟进）；wire_size / fit_wire_budget 函数体逐字迁移，read_file_contexts 行为不变。
- **全量**：pytest **1369 绿**（基线 1369，用时 36.6s）+ `mypy src` 38 文件干净。
- **文件边界**：git status 仅 budget.py（新建）+ llm.py + fix_errors.py + reference_library.py（仅注释两处）+ tests/test_llm.py + tests/test_fix_errors.py；generator/webapp/index.html/generate_check/selection/compile_runner 零改动。
- 取值推导单源入 budget.py：题面 4000 全中文 base 实测 53168 + 全文段壳 157 + 截断标注 244 → 67000 = 128KB − 10KB − 53.2KB − 0.4KB；`CLARIFICATION_HISTORY_CAP` 保留字符口径 2500，推导改按 6B 计。

## 现状证据（2026-08-14 读码核实）

- `llm.py:1365` `body_bytes = json.dumps(payload).encode("utf-8")`（ensure_ascii 默认 True，中文 \uXXXX 6 字节）；超 MAX_REQUEST_BYTES 即抛「请求体过大」（:1366-1373）。
- `tests/test_llm.py:3316-3331`：`reference_fulltexts={"big-ref": "中" * REFERENCE_FULLTEXT_CAP}` 全中文 fixture，断言 `len(prompt.encode("utf-8")) < MAX_REQUEST_BYTES`——测的是 UTF-8 3B，不是实发 6B。同文件 :3338-3350 clarify 用例同口径。
- 修复侧对照：`tests/test_llm.py:781-806` fix 最坏形态用「每行 50 中文 × 3000 行」全中文 fixture + json.dumps 口径——正确先例，照抄。
- 两套 cap 注释互指协调：`llm.py:256-273`（fix 预算反推，点名 `fix_errors.FIX_CONTEXT_TOTAL_BYTES`）↔ `fix_errors.py:72-80`（镜像注释）。无共享代码。
- `reference_library.py:448,458` 仅在注释提到 `llm.REFERENCE_FULLTEXT_CAP`（无实际 import）。

## 设计定案（已代决，实施会话不再重开）

1. **新叶子模块 `src/contest_generator/budget.py`**（不 import 任何域模块——防环：library→llm→fix_errors 链约束，叶子才能三方共享）：
   - `wire_size(content) -> int`：`len(json.dumps(content, ensure_ascii=True)) - 2`，逐字迁自 `fix_errors._wire_size`（`fix_errors.py:352-358`）。
   - `fit_wire_budget(content, budget) -> str`：二分取预算内最长前缀，逐字迁自 `fix_errors._fit_wire_budget`（`fix_errors.py:361-376`）；截断标注文案自身的 wire 字节计入预算（对齐 fix 侧 `read_file_contexts` 既有做法）。
   - 常量迁入：`FIX_CONTEXT_TOTAL_BYTES = 23000`（自 `fix_errors.py:82`）、`FIX_PREVIOUS_FIXES_CAP = 2500`（自 `llm.py:274`）；新增 `REFERENCE_FULLTEXT_BYTES`（推荐侧全文注入 wire 字节预算，取值按下条反推）。
   - `llm.py` / `fix_errors.py` 从 budget import 并 **re-export**（`from .budget import ...`），既有测试 import 面不动。
2. **推荐侧全文注入改 wire 字节预算**：`_selection_user_prompt` 的 reference_fulltexts 注入段弃用字符 cap `REFERENCE_FULLTEXT_CAP`（常量删除），改 `fit_wire_budget(..., REFERENCE_FULLTEXT_BYTES)`（截头带标注，TRUNCATION_NOTICE 文案沿用）。取值反推：MAX_REQUEST_BYTES − 最坏基础段（题面 4000 中文 24KB + 摘要 14 条 + 词表 + 澄清历史 2500×6B + 契约文本 + 系统提示词 + JSON 壳）− 余量 ≥10KB；推导注释单源入住 budget.py（写法参考 `llm.py:256-273`，全中文最坏口径）。`CLARIFICATION_HISTORY_CAP` 保留字符口径与 2500 值（历史只作「已答不重问」判据），推导按 6B 计。
3. **结构测试换口径（红证先行）**：`tests/test_llm.py:3316/3338` 两用例断言改 json.dumps 口径（同 :781 fix 先例的算法），fixture 保持全中文。**先只换口径不动实现 → select 用例必红（≈250KB > 128KB）** → 实施后绿 + `REFERENCE_FULLTEXT_BYTES` 改大即红（同 fix 侧钉法）。fix 侧结构测试（:781）零改动必须逐字节保持绿（共享化 = 逐字迁移）。
4. `llm.py:256-273` 与 `fix_errors.py:72-80` 镜像注释删除（推导单源进 budget.py）；`reference_library.py:448,458` 注释同步（仅注释）。

## 实施边界

- src：新 `src/contest_generator/budget.py` + `src/contest_generator/llm.py` + `src/contest_generator/fix_errors.py` + `src/contest_generator/reference_library.py`（仅注释两处）。
- tests：`tests/test_llm.py`（结构测试口径 + 新常量红证）+ `tests/test_fix_errors.py`（如 import 面变化）+ 实施时 grep `REFERENCE_FULLTEXT_CAP` 全部引用处收口。
- **零改动**：generator.py / webapp.py / index.html / selection.py / generate_check.py / compile_runner.py / 前端——本工单不碰（并行工单文件边界）。

## 验收标准

- [x] 红证：只换结构测试口径 → select 最坏用例跑红（256001 字节 > 120832，记录见验收记录）
- [x] 实施后：select/clarify 结构测试绿（json.dumps 口径，余量 ≥10KB）+ REFERENCE_FULLTEXT_BYTES 改大即红
- [x] fix 侧结构测试逐字节不变绿（共享化零回归）
- [x] 全量 pytest 绿（1369）+ `mypy src` 干净
- [x] `git status` 只出现预期文件

## 实施提示词（新会话粘贴）

> 工单：`.scratch/budget-wire-unification/issues/01-unify-wire-accounting.md`（先读全文，设计已定案勿重开）。
> 环境：`cd C:\Users\luoji\Desktop\firstep` → `git worktree add ../firstep-wt-budget-wire -b budget-wire-unification-01` → `cd ../firstep-wt-budget-wire`（必须独立 worktree，主检出有并行工单）。
> 文件边界：只动 `src/contest_generator/budget.py`（新建）+ `llm.py` + `fix_errors.py` + `reference_library.py`（仅注释）+ `tests/test_llm.py` + `tests/test_fix_errors.py`（如需）；generator.py / webapp.py / index.html / generate_check.py / selection.py / compile_runner.py 一个都不碰。
> 红证先行：先换结构测试口径跑红（记录字节数）再实施。共享化 = 逐字迁移，fix 侧结构测试必须零回归。
> 验收：红证记录 + 结构测试绿 + 新常量改大即红 + 全量 pytest 绿 + `mypy src` 干净；提交格式 `refactor: ...（工单 budget-wire-unification/01，N 绿 + mypy src 干净——...）` + docs 一笔；`gh pr create --body-file`（反引号坑）；不 force push；证据写本文件 Comments，Status → resolved，推送。

## Comments

## Comments

- 2026-08-14 已实施并推送：PR #68（https://github.com/AK47n/firstep/pull/68），分支 budget-wire-unification-01 两笔提交（refactor 20b7ff4 + docs 9d2fe70），未 force push，待合 main。
