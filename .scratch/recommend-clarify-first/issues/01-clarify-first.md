# 01 — 推荐先澄清后收敛（补问不再作废已跑轮次）

**What to build:** 现状补问发生在收敛循环中途：`select_modules_convergent` 第 N 轮模型输出 questions → 本轮即停、流以 question 事件收尾 → 用户回答后前端把回答拼进题面**重新从第 1 轮跑**——已跑轮次全部作废（用户实测：每轮约 2 分钟，跑两轮后重跑非常恼火）。本工单把推荐拆成两阶段：**澄清阶段先行**（带问答历史追问，直到模型不再有疑问），**收敛阶段后置**（澄清完后才进 4 轮循环，两轮一致提前停，期间不再被打断）。收敛阶段内模型若仍冒出新问题（罕见兜底）：照旧 question 收尾，答案并入历史重发——此时澄清通常已空，立即进收敛。

**Blocked by:** 无

**Status:** resolved（2026-08-10 实施，独立 worktree 分支 worktree-recommend-clarify-first，973 绿 + mypy src 干净）

## 需求

1. **LLM 协议加澄清调用**（llm.py，机械提取层）：
   - `LLM` Protocol 新增 `clarify(problem_text: str, clarifications: Sequence[tuple[str, str]]) -> tuple[str, ...]`：只看题面 + 已有问答历史，输出仍存的疑问（空 = 澄清完成）。**不传模块库**——疑问来自题面证据不足，与库无关（库内有没有实现是收敛阶段的事）。
   - DeepSeekLLM 实现：新系统提示词（CLARIFY_SYSTEM_PROMPT：你是电赛助手，逐句核对题面，证据不足以判定时向用户补问，不要重复用户已回答过的问题，没有疑问输出空 questions 数组）；用户消息 = 题面 + 逐条 `Q: … A: …` 历史；JSON mode 解析 `{"questions": [...]}`。
   - fakes.py FakeLLM 同步实现（可注入 questions，记录调用）。
2. **澄清阶段先行**（webapp.py `/api/recommend`）：
   - 请求体新增可选 `clarifications`（缺省空 = 向后兼容）：`[{question, answer}]`，校验字符串对。
   - run() 内先跑澄清：`llm.clarify(problem_text, clarifications)` 非空 → `emit.question({"questions": [...]})` 收尾流（不发 round 事件——澄清阶段不属于收敛轮次）。
   - 澄清空 → 进 `select_modules_convergent`（原流程不动）。
3. **收敛阶段 questions 兜底不变**：select_modules_convergent 内模型输出 questions（罕见）→ 照旧本轮即停返回 → webapp 转 question 事件收尾（现状行为保留）。
4. **前端**（index.html）：
   - 新增 `let recommendClarifications = []`（`{question, answer}` 历史），随 /api/recommend 请求体发送。
   - question 事件：回答输入框的「补充回答并继续」点击后把 `{question: <本次问题>, answer: <回答>}` push 进历史，再 `startRecommend(problem)`（**不再把回答拼进题面字符串**——历史走请求体，题面保持原文，避免题面污染收敛判定的句子编号稳定性）。
   - 手动重新点「让 AI 推荐」时清空历史（新生命周期）。
5. **测试**：
   - test_llm.py：clarify 提示词契约（含历史逐条、不重复已答问题指令）与 JSON 解析（空数组 → 空元组）。
   - test_selection.py 或 test_webapp.py：澄清阶段——FakeLLM.clarify 返回非空 → 事件序列 `[question]`（无 round，无 done）；带 clarifications 重发且 clarify 返回空 → 进收敛 → `[round, …]` done。
   - 回归：收敛阶段内 questions 兜底路径（现有 test_recommend_question_ends_stream_with_question_event 补 clarify 默认空，事件序列 `[round, question]` 不变）。
6. **CONTEXT.md**：收敛循环词条补"澄清阶段先行（补问在收敛前完成，回答后不重跑已跑轮次）"。

## 文件边界

- `src/contest_generator/llm.py`：+CLARIFY_SYSTEM_PROMPT、Protocol +clarify、DeepSeekLLM.clarify
- `src/contest_generator/webapp.py`：/api/recommend 读 clarifications + 澄清阶段先行（run 内）
- `src/contest_generator/static/index.html`：clarifications 状态 + question 处理 + 请求体
- `tests/fakes.py`：FakeLLM +clarify
- `tests/test_llm.py` / `tests/test_webapp.py`（或 test_selection.py）：契约 + 流程测试
- `CONTEXT.md`：词条补句
- 注意：selection.py 不动（收敛循环本身无改动；澄清是 llm 层调用 + webapp 编排）

## 验收

- [x] 全量测试绿 + mypy 干净（973 passed = 基线 956 + 17 新测试；mypy src 32 文件零问题）
- [x] 澄清阶段：clarify 非空 → 事件序列 `[question]`（无 round / done）；空 → 进收敛
- [x] 带 clarifications 重发：澄清空 → 立即进收敛（`[round, round, converged, done]`，不重跑澄清轮次语义）
- [x] 兜底路径回归：收敛内 questions → `[round, question]`（现状 test_recommend_question_ends_stream_with_question_event 原样过）
- [x] 前端：回答后历史 push `{question, answer}` 随请求体发送，题面保持原文（收敛收到的题面仍是逐句编号原文，断言回答不在其中）
- [x] CONTEXT.md 收敛循环词条补"澄清阶段先行（补问在收敛前完成，回答后不重跑已跑轮次）"
- [x] 独立 worktree（../firstep-clarify-first）+ 独立 commit

## Comments

- 2026-08-10 立项（用户会话直接提需求，方案经确认）：四问代决——① 澄清放收敛前（用户诉求"先把问题问完再跑四轮"）；② 澄清调用不带模块库（疑问源自题面证据不足，与库无关，成本更低）；③ 兜底路径 = 收敛内 questions 照旧收尾、回答并入历史重发（用户确认可接受：罕见路径，且此时澄清通常已空）；④ 回答走请求体 clarifications 而非拼进题面（拼题面会破坏收敛判定的句子编号稳定性——收敛对照依赖逐句编号）
- 2026-08-10 实施闭环：llm.py（CLARIFY_SYSTEM_PROMPT + Protocol/DeepSeekLLM.clarify + parse_clarify_questions 严格解析 + _clarify_user_prompt：题面截断带标注 + 逐条 Q/A 历史）；webapp /api/recommend 读 clarifications（_require_clarifications 字符串对校验，answer 允许空串 = 用户明确不给补充，防澄清死循环）→ run() 内先 clarify：非空 question 收尾（不发 round）、空进收敛；clarify 与收敛共用同一 _llm 实例（工厂每次请求构造，两次调用会拿到两个实例——顺带修掉）；前端 per-question 独立回答输入（多问不再共享一个回答）、回答 push 进 recommendClarifications 随请求体重发、手动重推清空历史；RaisingLLM / ScriptedDistillLLM 补 clarify（保持"实现协议全部方法"声明诚实）。验证：973 绿 + mypy src 干净；澄清阶段 `[question]`（无 round）/ 带历史澄清空 `[round, round, converged, done]` 且收敛题面仍是逐句编号原文 / 兜底 `[round, question]` 回归不变。
