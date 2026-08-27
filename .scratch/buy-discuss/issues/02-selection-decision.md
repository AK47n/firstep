# 工单 02：结论模型承接 + 提示词注记（selection / context）

> 来源：.scratch/buy-discuss/spec.md §2.3-2.4
> 状态：resolved（双轴评审通过 + 整改：Standards 5 项 / Spec 3 项，E2E 10/10）

**要做什么：**
- `selection.py`：`SuggestionDecision` @dataclass(frozen)：source（wordlist | custom，词表外修正 wordlist）/ name / note / verdict（可选，三档词表）；`OutOfLibrarySuggestion` 加 `decision: SuggestionDecision | None = None`（从载荷 item 解析：decision 非对象/缺 name = 置 None 不报错——展示增强不阻断导览）；`to_dict` 带出 decision（None = 旧载荷逐字节）。
- 提示词注记（`_requirement_lines` 系 / plan_tasks / execute_task / deepen 共用的需求行装配）：suggestion 带 decision 时追加：
  - wordlist：「（已定：<方案名>，<接口>/<价格>）」；
  - custom：「（已定：<name/note>，AI 审核：<verdict>）」。
- 不动生成/骨架选择逻辑（范围外：结论不反向改模块集）。

**被谁阻塞：** 01（协议）。

**验收标准：**
- [x] SuggestionDecision 解析/默认/词表外修正/to_dict 缺省逐字节
- [x] 需求行注记两形态（wordlist / custom）单测
- [x] tests/test_selection.py + test_llm.py 相关绿；中文 commit（工单 02）
