# 01 — apply_fixes 匹配决策剥离（match_snippet 纯函数接缝，架构评审卡 3）

**What to build:** 把 apply_fixes 写回循环内联的匹配决策（fix_errors.py:427-484：精确子串 vs 行首前缀归一化 vs 歧义/未命中的判决分支 + 理由文案）抽成纯函数接缝 `match_snippet`（片段 + 文件内容 → 命中判决 + 替换区间），写回循环只消费判决；匹配语义、协议（FIX_SYSTEM_PROMPT）、理由文案各自单源且可测。**行为零变化**：判决语义、applied/skipped 结果、reason 文案、备份/顺序写回全部不变。

**Status:** resolved

**来源：** 架构评审 2026-08-12 卡 3（评审唯一剩项）。fix-snippet-match/01 已抽辅助函数（_snippet_normalized_lines / _normalized_hits / _line_span / _preserve_line_ending），但「用哪种策略」的判决仍内联在写回循环——改匹配规则要动 apply_fixes 函数体 + FIX_SYSTEM_PROMPT + 理由文案三处，且匹配语义无法脱离文件系统单独测。

**决策记录（2026-08-13，用户授权代决）**

1. **判决形态：单一 dataclass `SnippetMatch`**——status（"exact" / "normalized" / "none" / "ambiguous"）+ start / end（替换区间，仅 applied 时有效）+ snippet（替换文本，仅 applied 时有效）+ count（歧义/未命中的计数，文案用）。对照现状：count==1 → exact；count==0 → 归一化（1 命中 → normalized，0 → none，>1 → ambiguous）；count>1 → ambiguous。
2. **语义逐字迁移，不改良**：exact = 子串区间替换（new_snippet 原样）；normalized = 行区间 + `_preserve_line_ending`（「按行首前缀归一化匹配应用」）；none/ambiguous 的 reason 文案逐字保持（三条 skipped 文案 + 一条 normalized applied 文案）。剥离不是改规则，是搬家。
3. **理由文案单源：`_reason_for(match) -> str` 模块级小纯函数**——status → 文案（含 count 插值），apply_fixes 只调它，文案可单测；将来改文案只动一处。
4. **协议对偶钉住**：FIX_SYSTEM_PROMPT 约束 2（llm.py）文本**不动**（协议未变）；新增对偶断言——prompt 含协议关键语义（行首前缀归一化 / 唯一匹配）且 match_snippet docstring 同款描述（照 test_generate_check_contract 词表对偶先例），改一侧即红。
5. **测试迁移**：fix-snippet-match/01 的红证用例全集（丢缩进 / 丢行尾注释 / CRLF / 行内多空格 / 歧义跳过 / 本体差异跳过 / 多行块 / 删整行）挂到 match_snippet 直测（纯函数，不碰文件系统）；apply_fixes 层保留端到端行为用例（写回 + 备份语义不回归）；结构钉：apply_fixes 体内不再直调 `content.count(fix.old_snippet)` / `_normalized_hits`（判决只经 match_snippet）。
6. **不动**：写回编排（备份 / 顺序写回 / 新内容演化）、路径判决（_validate_fix_file）、run_fix_round、webapp、llm 协议文本、前端。

## 实施（文件边界）

1. **`src/contest_generator/fix_errors.py`**：
   - 新增 `SnippetMatch` dataclass（模块已有 dataclass 风格，放 FixResult 附近）+ `match_snippet(content: str, old_snippet: str, new_snippet: str) -> SnippetMatch`（纯函数，零文件系统，语义逐字迁自 apply_fixes 427-484 的判决分支；docstring 写明判决契约）+ `_reason_for(match: SnippetMatch) -> str`（三条 skipped 文案 + normalized applied 文案逐字保持，count 插值不变）；
   - apply_fixes 写回循环瘦身：`match = match_snippet(content, fix.old_snippet, fix.new_snippet)` → switch status（exact/normalized = applied，用 match.start/end/snippet 替换 + reason=_reason_for 或空；none/ambiguous = skipped + reason=_reason_for）。
2. **`src/contest_generator/llm.py`**：FIX_SYSTEM_PROMPT **不动**（协议文本原样；若对偶测试需要可提取约束 2 词段常量，可选）。
3. **`tests/test_fix_errors.py`**：
   - 新增 match_snippet 直测（纯函数）：四形态红转绿用例（丢缩进 / 丢行尾注释 / CRLF / 行内多空格 → normalized + 区间 + snippet 语义）+ 歧义（exact 多处 / normalized 多处 → ambiguous + count）+ 本体差异（→ none）+ 多行块 + 删整行（new_snippet="" 区间语义）；
   - 新增 _reason_for 文案断言（四条文案逐字）；
   - 协议对偶断言（prompt 词表 ↔ match_snippet docstring）；
   - 结构钉：apply_fixes 体内无 `content.count(` / `_normalized_hits(` 直调（AST 切片，对照既有结构钉风格）；
   - 既有 apply_fixes 端到端用例（写回 / 备份 / 回滚链路）保持全绿——行为不回归验证。
4. **不动**：webapp / compile_runner / run_fix_round / 前端 / 生成器。

## 验收

- [x] `pytest` 全绿（基线 1247 + 新增/迁移）+ `mypy src` 干净 + node 过（前端零改动）
- [x] match_snippet 直测绿（红证先行：抽离前无此函数）
- [x] apply_fixes 端到端行为不回归（applied/skipped/reason 文案逐字不变 + 备份/回滚照常）
- [x] 结构钉绿（写回循环不再直调匹配原语）

## 实施记录

- 2026-08-13 已实施（1260 绿 = 基线 1247 + 新增 13；`mypy src` Success 36 files；
  node 9 过——`node --test tests/js/sse-parser.test.mjs` 显式文件路径，Git Bash 下
  目录参数被当模块解析报 MODULE_NOT_FOUND，非代码问题；前端零改动）：
- fix_errors.py：新增 `SnippetMatch` dataclass（FixResult 附近，四态 + 替换区间 +
  count）+ `match_snippet` 纯函数（零文件系统，判决语义逐字迁自原 427-484：
  精确 1 次 → exact / 精确 0 次走归一化（1 命中 → normalized / 0 → none / >1 →
  ambiguous）/ 精确 >1 次 → ambiguous，替换区间与行尾保护原样）+ `_reason_for`
  单源（exact 无文案、normalized 标注、三条 skipped 文案逐字，count 插值不变）；
  apply_fixes 写回循环瘦身为 switch 消费判决（applied 用 match.start/end/snippet
  替换，skipped 用 _reason_for）；模块 docstring / apply_fixes docstring 指向接缝。
- **实施补录（决策张力）**：决策 1 枚举四态 status，但决策 3「三条 skipped 文案
  逐字保持」要求区分两种歧义（精确多处 vs 归一化多处）——两者 status 同为
  "ambiguous" 而文案不同。补 `via_normalized: bool = False` 判别字段（True = 归一化
  多处命中），仅 _reason_for 消费，apply_fixes 与状态枚举不受影响。
- 测试 +13：match_snippet 直测 9（丢缩进 / 丢行尾注释 / CRLF / 行内多空格 →
  normalized + 区间 + snippet 语义逐字，exact 子串区间，双歧义 count + 来源判别，
  本体差异 → none，多行块整块区间，删整行空 snippet）+ _reason_for 四条文案逐字
  锚定 1 + 协议对偶 1（FIX_SYSTEM_PROMPT 约束 2 词表「行首前缀归一化 / 唯一匹配」
  双端断言，照 test_generate_check_contract 先例）+ 结构钉 1（apply_fixes 函数体
  AST 钉：content.count( / _normalized_hits( 直调即红 + 正向钉 match_snippet 调用
  在）。红证：match_snippet 抽离前不存在，直测与对偶实施前必红。
- 端到端不回归：既有 apply_fixes 用例（精确写回 + 备份 / 归一化四形态 / 双歧义
  跳过 / 本体差异 / 多行块 / 删整行 / 同文件顺序写回 / 回滚链路 / run_fix_round
  事件序列）零改动全绿——reason 文案与磁盘字节逐字不变。
- 不动：llm.py（FIX_SYSTEM_PROMPT 协议文本原样）/ webapp / compile_runner / 前端
  / 生成器。
