# 01 — 推荐链路提速 + 预算兜底：一轮问全 + 有历史跳过澄清门 + 收敛提前停 + 请求体预算保证

**What to build:** `/api/recommend` 链路三处串行浪费 + 一处预算漏洞一起修（A/B/C/D，src 两个文件）：
- **A 一轮问全（提示词）**：澄清与选择两阶段都要求模型把全部疑问一次性列全，不再渐进式追问（2021F 补问 4 轮 10 条的历史教训）。
- **B 有历史跳过澄清门（编排）**：`clarifications` 非空时不再跑 `llm.clarify`，直接进收敛循环——每轮补问省一次串行 LLM 调用。
- **C 收敛提前停（修订提示词）**：轮间修订从"自检修订、输出完整新一层"改为核验式，让"两轮一致即停"真正生效，不再拖到 4 轮封顶。
- **D 请求体预算保证（bug 修复）**：`REFERENCE_FULLTEXT_CAP = 60000` 字符 × UTF-8 ≈180KB 单段就能撑爆 `MAX_REQUEST_BYTES = 128KB`——2026-08-13 真机实测 2021F 推荐 select 调用 192486 字节被预检拦死（模型点名大参考文件时必现，非偶发）。全文截断上限收到预算保证值（≤35000 字符）+ 澄清历史段补截断。

**Status:** claimed

**Blocked by:** 无。与在跑的 gen-check-fix-loop/01 重跑零文件重叠（对方只动 `.scratch/real-run/generate_check.py` + `tests/test_generate_check_contract.py`），可并行独立 worktree。

## 现状证据（2026-08-13 真机实测，并行会话 run1）

| 环节 | 耗时 | 占比 |
|---|---|---|
| 推荐 SSE 流（真实 DeepSeek，每轮 LLM 2-4 min × 4 轮/题） | 单题 ~10-15 min | ~90% |
| 骨架 1 次 LLM 调用 | ~1-2 min | ~8% |
| UV4 全量重建 / 生成+门禁 | 10-30 s | ~2% |

- 问答轮数：2021F 补问 4 轮 10 条。每轮 = 1 次 clarify 串行调用，最后一轮再叠加 2-4 轮收敛调用；`clarify` 只问"题面证据不足"，看历史问答后仍会问**新**问题——渐进式追问是轮数多的根因。
- 收敛轮数基线（`.scratch/real-run/*.log` 首行 `[推荐] N 轮`）：check_2024H **4 轮**、check_2026C_t1 **4 轮**、check_2021F_t1 3 轮、green_2021F_stm32 2 轮——多数跑满 `SELECT_CONVERGENCE_MAX_ROUNDS = 4` 封顶，收敛判定（两轮功能需求层一致即停）没生效。**2026-08-13 T3 验收回归中 2026C 以 2 轮收敛**（同题历史 4 轮）——轮数有模型波动，C 的目标是让 2-3 轮成为常态。
- **D 预算漏洞实测（2026-08-13 T3 验收回归）**：2021F select 调用 `192486 字节 > 131072`（3 次重试同尺寸 = 确定性，非偶发）。构成实测：stm32 模块摘要 14 条 1.6K 字符、词表段 250 字符、澄清历史 12/20 条均 ~9K 字节、无参考段用户提示词 ~20KB——大头 = 参考全文段（`REFERENCE_FULLTEXT_CAP = 60000` 字符 ≈ 180KB 单段上限 > 128KB 总量上限，预算数学自相矛盾）。
- `selection.py:_revision_prompt` 让模型每轮"自检修订，输出完整的新一轮功能需求层"——模型每轮都改，`_functional_layer_key` 永远不一致 → 拖到封顶。
- `run_recommendation`（selection.py:856）每次先跑 `clarify`，即使历史已答过；有历史时 `select_modules` 已带历史段 + "已答不重问、仅补新疑问"（SELECT_SYSTEM_PROMPT），clarify 的补问功能被 select_modules 覆盖——门是冗余的。

## 决策记录（代决，用户可 grilling）

1. **A 一轮问全**：`CLARIFY_SYSTEM_PROMPT` + `SELECT_SYSTEM_PROMPT` 各补一句——有疑问时一次性把所有疑问全部列出（宁全勿漏、每条具体可答、**最多 10 条**），用户一轮全部答完；不要分批渐进追问。上限 10 条防问题轰炸。
2. **B 跳过澄清门**：`run_recommendation` 里 `clarifications` 非空时不调 `llm.clarify`，直接进 `select_modules_convergent`。无历史（首跑）仍 clarify 先行——廉价的证据缺口门保留。风险自担点：答案没清完疑问时，新问题会在一轮收敛（贵调用）后才浮现——被 A 摊薄（一轮问全后答案不全罕见），可接受；`select_modules` 本身会补问，不会漏问。
3. **C 收敛提前停**：`_revision_prompt` 改为核验式——"逐条核验上一轮功能需求层，题面原文是唯一裁判：仅当有确凿题面证据表明错误（脑补/遗漏/覆盖错）才改对应条目，其余条目原样保留输出；无证据支持的改动本身是脑补"。SELECT_SYSTEM_PROMPT 的"反复自检修订"不动（那是单轮内行为）；`max_rounds=4` 封顶不动（质量兜底）。
4. **D 预算保证**：`REFERENCE_FULLTEXT_CAP` 60000 → **35000**（35000 × 3B ≈ 105KB + 基础段 ~25KB ≤ 128KB 恒成立，留余量）；澄清历史段（`_selection_user_prompt` / `_clarify_user_prompt` 的 Q/A 循环）补 `_truncate_content` 截断（历史随补问轮数无界增长，是预算第二大漏点——当前 20 条 ~9KB 尚可控，防未来涨）。结构测试钉住不变量：最坏情况用户提示词（35000 字符全文 + 截断后历史 + 词表 + 摘要）序列化 < MAX_REQUEST_BYTES——cap 再改大即红。
5. **范围外**：同题缓存（另立 check-recommend-cache 工单）、流式输出、更快模型档位、max_rounds 下调。

## 实施

1. **`src/contest_generator/llm.py`**：
   - CLARIFY_SYSTEM_PROMPT（~101 行）/ SELECT_SYSTEM_PROMPT（~78 行）措辞（A）。
   - `REFERENCE_FULLTEXT_CAP` 60000 → 35000（D）；澄清历史段补 `_truncate_content`（D，`_selection_user_prompt` ~1713 行与 `_clarify_user_prompt` ~1644 行两处 Q/A 循环）。
2. **`src/contest_generator/selection.py`**：
   - `run_recommendation`：`if not clarifications:` 才跑 clarify 门（B，docstring 同步——"澄清阶段先行"的表述改准确）。
   - `_revision_prompt`：核验式措辞（C）。
3. **`tests/test_llm.py`**：提示词契约断言同步（`test_clarify_prompt_contract` 先例；select 提示词若有双端断言一并同步）；D 结构测试——最坏情况用户提示词（REFERENCE_FULLTEXT_CAP 上限全文 + 截断后历史 + 词表 + 摘要）序列化 < MAX_REQUEST_BYTES（红证先写：把 cap 拉回 60000 跑红）。
4. **`tests/test_selection.py`**：
   - B：`clarifications` 非空 → fake `clarify_calls` 为空 + 直进收敛（select 被调、kwarg 带历史）；无历史 → clarify 仍先行（回归不变）。
   - C：`_revision_prompt` 文本契约（若既有断言存在则同步）。

### 实施注

- fakes.py 的 `clarify_calls`（fakes.py:611）已记录调用，B 的断言直接用；select 调用记录同款先例（fix_errors_calls 第 7 元）。
- A 的措辞改动会红测试里的逐字断言——先跑红、再同步，别顺手改别的。
- C 是提示词行为，效果只能真机观察；本工单不承诺轮数必降，但验收要求记录对比。
- D 的 35000 推导：35000 字符 × 3B/字符（UTF-8 中文/代码最坏）= 105KB + 基础段（摘要 5KB + 历史截断后 ~9KB + 题面 3KB + 系统提示词/JSON 壳 ~8KB）= ~125KB < 128KB。结构测试是唯一硬保证，数值调整必须过它。

## 验收标准

- [ ] pytest 全绿（含契约测试同步）+ `mypy src` 干净
- [ ] 真机（真实 DeepSeek）：2026C / 2021F 各跑一次，记录对比——问答轮数（历史 4 轮 → 目标 ≤2）、收敛轮数（历史 4 轮 → 目标 ≤3）、UV4 0 错（质量不降硬标准）；数字写进本文件 Comments
- [ ] 首跑无历史：clarify 仍先行（回归不变，fake 测试已钉）
- [ ] `git status` 只出现预期文件（llm.py + selection.py + 两个测试 + 本工单文件）

## Comments
