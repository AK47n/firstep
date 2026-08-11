# 01 — 收敛循环携带澄清历史（换措辞反复补问闭环断裂）

**What to build:** 澄清历史只进澄清阶段（`llm.clarify` 带 clarifications），**收敛循环不携带**——`select_modules_convergent` 每轮调 `llm.select_modules` 时 prompt 里没有问答历史。模型在收敛阶段对同一证据不足点补问（selection.questions → question 事件）→ 用户回答 → 前端重推（clarifications 追加）→ 澄清阶段看到历史答"空"进收敛 → **收敛阶段又看不到答案，换措辞再问同一问题**——问答闭环断裂。真机实测（2026C 双选，工单 generate-check-parity/01 验收记录）：模型对题面"序号2缺失"换措辞反复补问，clarify_2026C.json 加映射只防澄清阶段，防不了收敛阶段。目标：clarifications 透传进收敛循环每轮 `select_modules` 的 prompt（题面后附"已澄清问答"独立段），`SELECT_SYSTEM_PROMPT` 补"已答过的问题不要重复问"。

**Status:** implemented（2026-08-11，pytest 1081 绿 + mypy 干净 + 真机 2026C 双选收敛闭环）

## 实施记录（2026-08-11）

- **llm.py**：`select_modules` 加 `clarifications: Sequence[tuple[str, str]] = ()`（缺省空 = 旧行为，与 manual_fulltexts 同规）；`_selection_user_prompt` 在参考段 / 手动全文段之后、词表段之前附"用户已澄清的问题（题面证据不足处用户已补充的回答，不要重复问）"独立段——Q/A 逐条、保序、空历史不出段、不并入题面（题面逐句编号跨轮稳定，收敛判定的对照句编号依赖它）；`SELECT_SYSTEM_PROMPT` 补"用户已回答过的问题不要重复问，仅补充新疑问（与澄清阶段同规，问答历史在题面后的独立段）"——与 `CLARIFY_SYSTEM_PROMPT` 同款措辞（两阶段语义一致）。LLM Protocol 同步补参数。
- **selection.py**：`select_modules_convergent` 加 `clarifications` 参数，每轮 `llm.select_modules` 透传（4 个调用点全覆盖，含两级注入的第一/二级与无参考路径）；`run_recommendation` 传给 `select_modules_convergent`。透传用"非空才传关键字"条件（`optional_kwargs` 单次 `**` 展开）——缺省空 = 旧签名调用（既有假 LLM 零改动）。**坑**：手动全文与澄清历史两个异构 `**dict` 分别展开时 mypy 按位置错配参数（manual_fulltexts 单展开先例只容一个），合并成单次 `dict[str, Any]` 展开解决（注释已记）。
- **测试**（+6，基线 1075 → 1081）：
  - test_llm.py：选择阶段 prompt 契约——历史段格式（Q/A 逐条、保序）/ 与题面分离（题面原样在前、无 Q/A 混入题面段、历史段不被编号）/ 缺省空不出段（回归钉死）/ SELECT_SYSTEM_PROMPT 与 CLARIFY_SYSTEM_PROMPT 同款"已答不重问"措辞。
  - test_selection.py：收敛透传——每轮 `select_modules` 收到同一份 clarifications（保序）；缺省空 = 旧签名调用（记录到空元组）。
  - test_webapp.py：闭环断言——收敛阶段补问 → question 事件 → 用户回答重推（clarifications）→ 第二次收敛每轮 select_modules 都收到首次答案（ClarifyHistoryTopicLLM 状态化假 LLM）；澄清阶段与收敛阶段看到同一历史（双阶段一致）。
  - fakes.py FakeLLM / test_webapp.py TopicAwareLLM 同步补 clarifications 参数（协议对齐，缺省空零行为变化）。
- **CONTEXT.md**：收敛循环词条补"澄清问答历史贯穿收敛循环（select_modules 每轮带 clarifications 独立段，题面编号不动）"。
- 不动：clarify 阶段 / build_module_selection / events.py / webapp.py / generate_check.py（--clarify 映射走同一 run_recommendation 路径，自动受益）。

## 真机验收记录（2026-08-11，已闭环）

- 重启 8000 服务（杀旧 PID 50208 → `PYTHONPATH=src python -m contest_generator.webapp`，新 PID 39432，`/api/tabs/register` 探活 405 = 路由在场）。
- `python generate_check.py 2026C --clarify clarify_2026C.json`（stm32/Keil 线，题面已补全 + clarify_2026C.json 6 条映射预置）：**补问归零**——4 次 recommend 尝试（全流程 1 次 + SSE 探针 3 次）终态要么 done 要么传输错，**一次 question 事件都没有**：收敛探针 4 轮 → done（此前 generate-check-parity/01 记录的"对题面序号2缺失换措辞反复补问"不再出现——澄清历史现在贯穿收敛循环，模型看到已答问题不再重问）。
- 全流程 ✓：推荐 done → 骨架 → 生成 44 文件（2026C 双选 zigbee_uart + zigbee_uart_key + zone + lock_control + filter 等）→ 产物门禁全过（产物树语料重建，与生成同源）→ **UV4 命令行构建 0 Error(s), 0 Warning(s)**（日志 .scratch/real-run/keil_build.log）。
- **遗留观察（非本工单范围）**：DeepSeek 偶发返回空内容（4 次 recommend 中 2 次"模型返回的不是 JSON："，空 detail = 响应 content 为空）——select_modules 走 `_chat` 单次调用无重试，收敛中途遇空响应即 error 终态。这是传输层鲁棒性缺口（与补问闭环无关，question 事件从未出现），建议另立工单：select_modules 空内容 / 畸形输出加重试（对齐 `_retry_parse` 的整次重试兜底）。

## 现状（已核实，2026-08-11）

- `run_recommendation`（selection.py:808-879）：澄清阶段 `llm.clarify(topic.problem_text, clarifications)` 带历史（838）；收敛 `select_modules_convergent(llm, topic.problem_text, ...)`（842-850）**不传 clarifications**。
- `select_modules_convergent`（706-797）：每轮 `llm.select_modules(round_topic, manifest_summaries, references, fulltexts)`（757/764/776/784）——签名无 clarifications，prompt 无历史段。
- `llm.select_modules`（576-625）：签名 `(problem_text, manifest_summaries, references, reference_fulltexts, manual_fulltexts)`；`_selection_user_prompt` 无历史段；`SELECT_SYSTEM_PROMPT`（80-97）无"已答不重问"句。
- 收敛阶段补问路径（真实存在的第二出口）：selection.questions → run_recommendation emit.question（851-853）→ 用户回答重推 → 澄清空 → 收敛循环 → 缺口重现。
- **编号稳定性约束**：收敛判定 `_functional_layer_key` 依赖题面句子编号跨轮稳定（723"编号跨轮稳定——收敛判定的对照句编号依赖它"）——历史段必须附在题面之后、独立成段、不带编号、不并入题面文本。
- 向后兼容基线：`clarifications` 缺省空 = 现状行为（既有 FakeLLM 调用零改动，与 manual_fulltexts 的缺省处理同规，selection.py:743-744）。

## 实施

1. **llm.py**：
   - `select_modules` 加 `clarifications: Sequence[tuple[str, str]] = ()` 参数（缺省空 = 旧行为）；`_selection_user_prompt` 在题面/参考段之后附"用户已澄清的问题"段（`Q: …\nA: …` 逐条，空则不出段）。
   - `SELECT_SYSTEM_PROMPT` 补一句："用户已回答过的问题不要重复问，仅补充新疑问"（与 CLARIFY_SYSTEM_PROMPT 102-107 同款措辞，保持两阶段语义一致）。
2. **selection.py**：
   - `select_modules_convergent` 加 `clarifications: Sequence[tuple[str, str]] = ()` 参数，每轮 `llm.select_modules` 透传。
   - `run_recommendation` 把 clarifications 传给 `select_modules_convergent`。
   - 题面编号不动（历史独立成段，不改 `_number_topic_sentences`）。
3. **测试**：
   - 选择阶段 prompt 契约：记录型假 LLM 断言 `_selection_user_prompt` 含历史段（格式 / 顺序 / 空历史不出段 / 与题面分离）。
   - 收敛透传：假 LLM 断言 `select_modules_convergent` 每轮 `select_modules` 收到同一 clarifications。
   - 闭环断言：模拟"收敛阶段补问 → 重推带历史"路径，第二次 run 收敛阶段 prompt 含首次答案。
   - 向后兼容：缺省空 = 既有测试零改动全绿。
4. **CONTEXT.md**：收敛循环词条补一句——"澄清问答历史贯穿收敛循环（select_modules 每轮带 clarifications 独立段，题面编号不动）"。

## 文件边界

- src/contest_generator/llm.py —— select_modules 签名 + _selection_user_prompt 历史段 + SELECT_SYSTEM_PROMPT 一句
- src/contest_generator/selection.py —— select_modules_convergent + run_recommendation 透传
- tests/test_llm.py + tests/test_selection.py —— prompt 契约 / 透传 / 闭环断言
- CONTEXT.md —— 词条一句
- **不动**：clarify 阶段（机制已对）、build_module_selection、events.py、webapp.py（前端已随请求体重发 clarifications）、generate_check.py（--clarify 映射经同一 run_recommendation 路径，自动受益）

## 验收

- [x] pytest 全绿（1075 基线 + 新增 6 = 1081，无回归）+ `mypy src` 干净（32 文件）。
- [x] 闭环断言证明：收敛阶段补问的答案在重推后进入收敛 prompt（test_recommend_convergence_ask_answers_carried_into_retry，第二次收敛每轮 select_modules 收到首次答案；prompt 历史段格式由 test_llm 契约钉死）。
- [x] 向后兼容：clarifications 缺省空 = 旧行为（缺省不出段 / 不传关键字，既有假 LLM 零改动，测试回归钉死）。
- [x] 真机：起服务 → 重跑 2026C 双选（题面已补全 + 历史贯穿）→ 不再换措辞反复补问（补问收敛或归零）→ 生成 + UV4 0 错 0 警；如补问仍在，记录剩余形态另立。（补问归零：收敛探针 4 轮 done、零 question 事件；全流程 UV4 0 Error(s) 0 Warning(s)；遗留观察 = DeepSeek 空内容偶发，另议。）
- [x] 工单补实施记录 + 验收勾选，Status implemented。
