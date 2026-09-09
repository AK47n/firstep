# 01 — 模块推荐候选预筛纯函数

**要做什么：** 让「预筛」成为可独立验证的纯函数：给定全量模块摘要（已按平台过滤）、题面、词表、预算，返回按题面命中得分降序（同分 slug 字典序）、按 wire 预算截断（带标注）且保底 ≥20 条的预筛子集；题面零外设词命中时返回原全量（零增量，向后兼容）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施记录：** `selection.py` 新增 `PreselectResult` + `preselect_module_summaries` + 私有辅助（`_preselect_score` / `_wordlist_hit_slugs` / `_term_matches_topic` / `_fit_summaries_by_wire`）；`budget.py` 新增 `MODULE_SUMMARY_BYTES = 40000`、`MIN_PRESELECT = 20`（附推导注释）；词表私有辅助经同包私有互导复用（events._emit 先例）。评审整改：词表挂接从「行级整行并集」改为「方案名级精确优先、行级兜底」（题面「继电器」不再给 motor/l298n/pca9685 一起加分）。测试 7 例全绿（tests/test_selection.py）；mypy 清零；test_selection / test_reference_library / test_llm 全量无回归。

- [x] `selection.py` 新增 `preselect_module_summaries(summaries, topic_text, hardware_words, budget_bytes)` 纯函数，无副作用、确定性输出（同输入同输出）
- [x] 题面侧词激活复用 `PERIPHERAL_TERMS` 单源（reference_library 词表，selection re-export），激活规则照 `related_references` 既有实现：英文词独立出现（数字尾巴兼容）、中文子串、同义词组去重
- [x] 模块侧匹配面 = slug + description + kits 拼接；词项匹配规则与 related_references token 规则同构（英文词边界 + 数字尾巴、中文子串）
- [x] 词表 lib_modules 挂接参与打分：题面命中词表行 category/models → 该行 solutions 的 lib_modules slug 计命中分（照词表行与题面文本的子串判定）
- [x] 打分 = 命中词项数（去重、同义词组计一次），不做加权；输出排序 = 得分降序 → slug 字典序
- [x] 截断：join 后按 `_fit_segment_wire` 以预算截断带标注（Truncation 契约照现有）；不足 `MIN_PRESELECT`（20）条时扩到前 20 条
- [x] 零命中（激活词集为空）：排序退化为 slug 序（零增量语义——预算内全量原样保序；超预算照常 slug 序截断 + truncated=True，物理约束不豁免）
- [x] `budget.py` 新增 `MODULE_SUMMARY_BYTES = 40000`（候选值）、`MIN_PRESELECT = 20`（保底下限），附推导注释指向 spec
- [x] `tests/test_selection.py` 纯函数测试：打分 / 排序确定性 / 截断标注 / 保底 / 零命中零增量 / lib_modules 挂接 / 中英文词规则；全部通过
- [x] 既有全量测试（test_selection.py / test_llm.py）无回归

- [x] `selection.py` 新增 `preselect_module_summaries(summaries, topic_text, hardware_words, budget_bytes)` 纯函数，无副作用、确定性输出（同输入同输出）
- [x] 题面侧词激活复用 `PERIPHERAL_TERMS` 单源（reference_library 词表，selection re-export），激活规则照 `related_references` 既有实现：英文词独立出现（数字尾巴兼容）、中文子串、同义词组去重
- [x] 模块侧匹配面 = slug + description + kits 拼接；词项匹配规则与 related_references token 规则同构（英文词边界 + 数字尾巴、中文子串）
- [x] 词表 lib_modules 挂接参与打分：题面命中词表行 category/models → 该行 solutions 的 lib_modules slug 计命中分（照词表行与题面文本的子串判定）
- [x] 打分 = 命中词项数（去重、同义词组计一次），不做加权；输出排序 = 得分降序 → slug 字典序
- [x] 截断：join 后按 `_fit_segment_wire` 以预算截断带标注（Truncation 契约照现有）；不足 `MIN_PRESELECT`（20）条时扩到前 20 条
- [x] 零命中（激活词集为空）：返回原全量（逐条原样保序）
- [x] `budget.py` 新增 `MODULE_SUMMARY_BYTES = 40000`（候选值）、`MIN_PRESELECT = 20`（保底下限），附推导注释指向 spec
- [x] `tests/test_selection.py` 纯函数测试：打分 / 排序确定性 / 截断标注 / 保底 / 零命中零增量 / lib_modules 挂接 / 中英文词规则；全部通过
- [x] 既有全量测试（test_selection.py / test_llm.py）无回归


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
