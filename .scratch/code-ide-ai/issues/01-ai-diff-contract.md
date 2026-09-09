# 01 — AI diff 契约解析与校验（fx 纯件）

**要做什么：** 新 fx 纯件（fx/ai-diff.js）：AI 回复文本 → 结构化 diff 解析
与校验（契约见 spec「一期 C2」）：`parseAiDiff(text)` → `{path, stats,
hunks}|null`（无 `<DIFF>` 块 → null；块内容 JSON.parse；结构校验：path
非空相对路径、stats 数字、hunks 数组、每 hunk {line 数字, title 字符串可空,
lines 数组 {kind:"ctx"|"del"|"add", text 字符串}}、kind 枚举外 → 整块视为
无效返回 null + console.warn 原因）。另 `selectionContextText(path, lang,
startLine, endLine, code)` → 用户消息选区引用拼装
（`【代码引用 · path · 第 a-b 行】\n```lang\n<code>\n````）。纯函数无副作用，
文件头中文注释 + window.Object.assign 暴露。

**被谁阻塞：** 无——契约 spec 已定稿，可立即开始（与 02 并行）。

**状态：** resolved

- [x] 验收 1：parseAiDiff 对合法 DIFF 块（含 TODO 标题/多 hunk）解析出
  {path, stats, hunks} 全字段。
- [x] 验收 2：无块/空块/非 JSON/结构非法/kind 越界 → null；非法输入不 throw。
- [x] 验收 3：selectionContextText 拼装含路径/行区间/语言 fence；行号 1 起。
- [x] 验收 4：node 单测全绿（tests/js/ai-diff.test.mjs，≥8 用例）。

**结论：** 已落地（双轴评审整改后）。

**fx/ai-diff.js（新）**：`parseAiDiff(text)`——首个 `<DIFF>...</DIFF>` 块
（块内允许 ```json 围栏 + 注释剥壳重试一次）→ JSON.parse → 结构校验：
path（isSafeRelPath 预筛）、hunk.line≥1 整数、title 可空字符串、lines 非空数组、
kind ∈ ctx/del/add、text 字符串、**每 hunk 至少 1 个非 add 行**（应用器需
ctx/del 匹配锚点——评审 s1 补强：全 add hunk 无法锚定应用，宁拒不收）→
**stats 派生自 hunks**（additions/deletions/hunks 计数自洽；不信任不校验
AI 提供的 stats 数值——LLM 计数常不准，与 main_diff/maincDiff 派生一致，
决策记录：issue 字面「stats 数字校验」由派生取代）；非法 → null 不 throw；
多块取第一个。`selectionContextText(path, lang, startLine, endLine, code)`
→ 「【代码引用 · path · 第 a-b 行】\n```lang\n<code>\n```」（lang 空 → c 兜底）。

**评审整改（s1 双轴）**：①test #1 第二 hunk 补 ctx 锚点（守卫语义正确，
测试未同步——评审抓出套件红）②isSafeRelPath **复刻后端 is_unsafe_path
四规则**（entry_store.py:145-152：正斜杠开头/含冒号/含反斜杠/split 空段或
.. 段——原实现拒绝任意 .. 子串误拒 `foo..bar.c`、漏检空段与中段冒号 ADS；
后端 _resolve_in_root 仍为权威兜底）③测试 import 改 default（仓库主流）。

**判断项记录**：①console.warn 按 issue 字面未加——守 fx 纯函数无副作用
约定，异常路径静默 null（接受偏离）②空 `hunks:[]` 返回合法空对象
（调用方判 `hunks.length===0`；后端 main_diff 无差异 None 微异无害）
③line↔lines 锚点对齐**不做解析器钉死**（决策：解析器无文件上下文无法验证
「line=首个非非 del 行新文件行号」；且后端 apply 以 old 段整行匹配为锚点、
line 仅展示语义——AI 行号错位天然免疫，钉死是假约束）。

**测试**：tests/js/ai-diff.test.mjs 11 用例全绿（含锚点守卫/多块取首/fence
围栏/注释剥壳/path 四规则）；全量 node 1049 全绿。

- [x] 验收 1：合法 DIFF 块（TODO 标题 + 多 hunk）→ {path, stats, hunks}
  全字段（stats 派生自洽）。
- [x] 验收 2：无块/空块/非 JSON/结构非法/kind 越界 → null 不 throw。
- [x] 验收 3：selectionContextText 拼装含路径/行区间/语言 fence；行号 1 起。
- [x] 验收 4：node 单测 11 用例全绿 + 全量 1049 回归绿。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点，复核工单自述）：
  `src/contest_generator/static/js/fx/ai-diff.js` 存在——`parseAiDiff`（16 行，
  首个 `<DIFF>` 块 → JSON.parse → 结构校验）、`selectionContextText`（65 行，
  「【代码引用 · path · 第 a-b 行】+ ```lang fence」）、辅助 `isPosInt`（72）、
  `isSafeRelPath`（77，复刻后端 `entry_store.is_unsafe_path` 四规则）。
  测试 `tests/js/ai-diff.test.mjs` 11 用例，实测 `node --test tests/js/ai-diff.test.mjs`
  全绿（本文件含在 39 passed / 0 fail 的一批里）。验收逐条对照：
  ① 合法 DIFF 块全字段（:20）✓ ② 无块/空/非 JSON/结构非法/kind 越界 → null 不 throw
  （:37/42/48/57/62）✓ ③ selectionContextText 路径+行区间+fence（:88/94）✓
  ④ 单测 ≥8 用例（实 11）全绿 ✓。附：工单「验收 4」计数 11 与实况一致。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
