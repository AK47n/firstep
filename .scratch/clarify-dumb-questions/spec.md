# Spec：澄清阶段「蠢问题」修复——题面截断预算 + 提示词加固

## 问题（用户报告）

「现在ai推荐问的有些问题很愚蠢比如小车运送药品至指定病房后需要点亮红色指示灯等待卸载，是否对指示灯的颜色和亮度有具体要求？这个问题前面都说了红色指示灯还问我颜色」

## 根因分析

- `_clarify_user_prompt`（llm.py:2883）用 `_truncate_content(problem_text)` 截断题面，预算
  `EMBEDDED_CONTENT_CAP = 4000` 字符（llm.py:365）——**题面只送前 4000 字符**。
- 典型电赛题面（如送药小车）4000+ 字符很常见：「红色指示灯」句若在截断点之后，模型
  **根本看不到**，且截断标注（TRUNCATION_NOTICE）明确告知模型「题面可能被截断」——
  模型问「颜色是否有要求」是信息缺失下的理性补齐行为，用户视角则视为蠢问题。
- 次要因素：CLARIFY_SYSTEM_PROMPT（llm.py:135-142）约束弱——只要求「题面证据不足以
  判定时补问」，未强制「题面已明确的细节绝不重复问」，模型容易把已明确项与未明确项
  捆在一起问（本例：颜色已给红色、亮度未给，模型捆成一条）。

## 方案（聚焦 clarify）

1. **题面预算提升**：新常量 `CLARIFY_TOPIC_CAP = 12000`（字符）。题面是澄清阶段的唯一
   依据，4000 太小。wire 账本：全中文 ensure_ascii 6B/字符 → 12000×6 = 72KB + 澄清历史
   段（CLARIFICATION_HISTORY_CAP=2500 → 15KB）= 87KB < MAX_REQUEST_BYTES 128KB ✓。
   `_clarify_user_prompt` 改走 `truncate_content(problem_text, CLARIFY_TOPIC_CAP)`
   （截断标注保留——超 12000 的极端题面模型仍知道不完整）。
2. **提示词加固**：CLARIFY_SYSTEM_PROMPT 增加硬约束——「题面已明确给出的细节（如已指定
   颜色/型号/数量/类型）绝不重复问；每条疑问必须针对题面未给出的关键信息；没有疑问
   输出空数组；宁缺毋滥」。
3. **范围外**：不改 select/骨架的题面预算（select 带参考全文注入，预算联动需统一记账，
   另开）；不改其他调用；不做启发式问题过滤（易误伤）。

## 验收

- `_clarify_user_prompt`：5000 字符题面 → 完整保留（无截断标注）；15000 字符题面 →
  保留前 12000 + 截断标注（fake transport 断言 user prompt 内容）。
- CLARIFY_SYSTEM_PROMPT 含「已明确」「绝不重复问」约束（契约断言）。
- 全量测试绿 + mypy 干净；重启服务生效。
