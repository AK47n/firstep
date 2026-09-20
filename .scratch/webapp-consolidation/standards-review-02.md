# 工单 webapp-consolidation/02 — Standards 轴评审（固定点 HEAD 68638782，工作树）

范围：`src/contest_generator/webapp.py`、新文件 `tests/test_llm_run.py`
（忽略另一会话在途的 `docs/agents/local-environment.md` 与 `.scratch/pdf-dup-verify/`）。

## (a) 硬违规（1 处）

**CONTEXT.md 未随本单更新**。依据 `docs/agents/workflow.md` Step 1「When domain terms get
resolved, update `CONTEXT.md` / `docs/adr/`」+ `docs/agents/domain.md`「概念不在词表 = 信号」；
同批次先例 = 工单 01（提交 d03fcb35）改接口的同时改了 CONTEXT.md。本单新造名词「观测单元 /
`LLMRun`」并把「建收集器 + 结算」收成 webapp 的单一出处，而 CONTEXT.md 的「进度事件」行正是
这条链（collector → llm_telemetry → recent_llm_workflows）的口径处，工作树里却零改动。
（边界可辩：`LLMRun` 也可视作纯实现缝。）

## (b) smell（判断题，3 条）

1. **Middle Man** — `_llm_run` 只做构造转发，而 `LLMRun` 已公开（测试两者都 import）；对照
   `_llm` 真在兜 1/2/3 参数兼容面。→ 调用点直接 `LLMRun(context, "recommend")`，删这层。
2. **Speculative Generality（同一事实两处存）** — `self.workflow = workflow` 全 `src` 零读取，
   唯一读者是新用例；工作流名本已由收集器持有（`collector.workflow_id`）。→ 删字段，用例改
   断言 `collector.workflow_id.startswith(...)`。
3. **Duplicated Code（说明文）** — 「从前 25 个路由各写一遍…漏一样不报错」在类 docstring、
   `_llm_run` docstring、测试文件头近逐字重复三遍。→ 理由留类 docstring 一处，其余指过去。

查过、无问题：docstring 点名的两条 `tests/test_webapp.py` 工厂契约用例真实存在（2507 / 2543）；
`recent_llm_workflows` 直用只剩 `settle()` 与只读端点；其余基线项（Mysterious Name /
Feature Envy / Data Clumps / Repeated Switches / Shotgun Surgery / Divergent Change /
Message Chains / Refused Bequest 等）未发现。

## 处置（实施者回填，2026-09-20）

- (a)：CONTEXT.md 的「进度事件」行已补——正文一句话说明观测装配单源（`webapp.LLMRun`：预算 +
  收集器 + 派发 + 结算四件事一处、原先 25 处手写；`.llm()` 现派发、`.settle()` 幂等、只观测的
  工作流不造模型；判据与红证在 `tests/test_llm_run.py`），「主要实现」列补 `webapp.py（LLMRun
  观测缝）`。
- (b)1：`_llm_run` 已删，25 处调用点直接 `LLMRun(context, "...")`（改名脚本逐处打印复核）。
- (b)2：`self.workflow` 已删；用例改为断言 `collector.workflow_id.startswith("tasks-plan:")`。
- (b)3：理由收敛到 `LLMRun` 类 docstring 一处；测试文件头改为指过去（工厂 docstring 随
  Middle Man 一并删除）。
