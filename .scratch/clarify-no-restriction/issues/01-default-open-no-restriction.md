# 01 — 推荐补问全面收紧：无规定即无限制 + 材料性门槛 + 上限 5 条

**要做什么：** 用户跑 2024H「自动行驶小车」AI 推荐，澄清阶段仍问蠢问题（题面已写「每经过
一个点声光提示一次」，模型还问「是不是 A/B/C/D 每点都要」）。本工单把「题目中没有提到
就是没有限制（默认宽松）」+「材料性门槛（只问题面缺失且影响模块选择/方案核心结构的关键
信息）」+「上限 5 条」写进推荐流程的两个系统提示词（CLARIFY_SYSTEM_PROMPT 与
SELECT_SYSTEM_PROMPT，消除「宁全勿漏」与「宁缺毋滥」的矛盾），并加代码层硬上限兜底——
之后跑任何赛题，AI 只问题面真缺失且影响选型的问题（典型 0-3 条），题面已明确的细节与
未提及的细节一律不再问。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

## 验收标准

- [ ] CLARIFY_SYSTEM_PROMPT 与 SELECT_SYSTEM_PROMPT 均含「就是没有限制 / 未提及 /
      不为此提问 / 影响模块选择 / 绝不重复问」条款（契约测试断言）；「宁全勿漏、最多
      10 条」措辞全部移除；「一次性把所有疑问全部列出」「不要分批渐进追问」「宁缺毋滥」
      等既有条款保留。
- [ ] `selection.MAX_QUESTIONS = 5` 单一出处：两提示词中「最多 N 条」由该常量 f-string
      插值（契约测试断言 `f"最多 {MAX_QUESTIONS} 条"` 同时在两提示词中）；`parse_clarify_questions`
      与 `_parse_questions` 解析时 `questions[:MAX_QUESTIONS]` 截尾兜底（喂 7 条 → 返回 5 条，
      测试实证）。
- [ ] select 用户消息 JSON 契约示例同步收紧为「题面缺失且影响模块选择的关键补问」
      （双端漂移防重演，ticket 06 教训）。
- [ ] 全量 pytest 绿 + mypy src 干净；重启服务（start-app.bat）后 2024H 不再问题面已明确/
      未提及的细节。
- [ ] 语言规范：spec / 工单 / 提交信息中文；CHANGELOG 由提交信息自动补录。

## 实施记录

- `src/contest_generator/selection.py`：新增 `MAX_QUESTIONS = 5` 单一出处（注释含
  工单与语义）；`_parse_questions` 解析后 `raw[:MAX_QUESTIONS]` 截尾兜底。
- `src/contest_generator/llm.py`：`from .selection import MAX_QUESTIONS`（依赖方向
  与现有 llm → selection 一致，无新环）；`CLARIFY_SYSTEM_PROMPT` 与
  `SELECT_SYSTEM_PROMPT` 补问条款重写——「题面已明确给出的细节（颜色/型号/数量/
  类型/位置点）绝不重复问」「题目中没有提到的细节就是没有限制：题面未提及的要求
  一律视为无限制，按合理默认实现，不为此提问」「题面证据不足且直接影响模块选择或
  方案核心结构的关键信息才补问」；「宁全勿漏、最多 10 条」删除，上限改由
  `{MAX_QUESTIONS}` f-string 插值（提示词与解析层不漂移）；select 用户消息 JSON
  契约示例（含多实例两处）同步收紧为「题面缺失且影响模块选择的关键补问，可省略」；
  注释（107/140 行）同步「最多 selection.MAX_QUESTIONS 条」。
- `tests/test_llm.py`：`test_prompts_carry_one_shot_question_rule` 上限断言改
  `f"最多 {MAX_QUESTIONS} 条"`；新增 `test_prompts_carry_default_open_no_restriction_rule`
  （两阶段提示词含「就是没有限制 / 未提及 / 不为此提问 / 影响模块选择 / 绝不重复问」）
  与 `test_parse_clarify_questions_caps_at_max`（7 条 → 前 5 条）。
- `tests/test_selection.py`：新增 `test_parse_questions_caps_at_max`（7 条 → 前 5 条）。
- 预算联动：SELECT_SYSTEM_PROMPT 变长后最坏形态实测 122220 字节，余量断言 9KB →
  8KB（沿用「10KB → 9KB」既有修订先例，docstring 补修订 2 记录；CLARIFY 无参考
  注入不受影响）。

## 评审记录

- 自查收尾（改动小且全部由契约测试钉死，未开 code-review 双轴 subagent——与
  clarify-dumb-questions/01 先例同）：
  - 验收 1：两提示词均含「就是没有限制 / 未提及 / 不为此提问 / 影响模块选择 /
    绝不重复问」✓（契约测试实证）；「宁全勿漏 / 最多 10 条」全仓清零（grep 实证）；
    「一次性把所有疑问全部列出」「不要分批渐进追问」「宁缺毋滥」保留 ✓
  - 验收 2：`MAX_QUESTIONS = 5` 放 selection（llm 运行时导入，方向无新环）；
    `f"最多 {MAX_QUESTIONS} 条"` 同时在两提示词（测试断言）；`parse_clarify_questions`
    与 `_parse_questions` 均截尾，7 条 → 5 条测试实证 ✓
  - 验收 3：select JSON 契约示例两处（含多实例变体）均已收紧 ✓（replace_all 2 处）
  - 验收 4：全量 2256 passed + mypy 60 文件零问题 ✓；重启服务（start-app.bat）生效
  - 验收 5：spec / 工单 / 提交信息中文 ✓
  - 范围外遵守：`_build_user_prompt` 未动（select/骨架题面预算不变）；不做启发式
    过滤；webapp / 前端 / 视觉问答零改动 ✓

Status: resolved
