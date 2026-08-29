# 工单 01：clarify 题面预算提升 + 提示词加固（llm.py 单文件切片）

Status: resolved
Depends: 无
Blocks: 无

## 目标

修澄清阶段蠢问题：题面截断预算 4000 → 12000（澄清唯一依据）+ CLARIFY_SYSTEM_PROMPT
强制「题面已明确的不重复问」。

## 改动点（全在 src/contest_generator/llm.py + tests/test_llm.py）

1. 常量 `CLARIFY_TOPIC_CAP = 12000`（放 EMBEDDED_CONTENT_CAP 附近，注释含 wire 账本）。
2. `_clarify_user_prompt`（llm.py:2879）：题面改走 `truncate_content(problem_text, CLARIFY_TOPIC_CAP)`
   （不再用 _truncate_content 的 4000；截断标注保留）。
3. `CLARIFY_SYSTEM_PROMPT`（llm.py:135）：加硬约束句——「题面已明确给出的细节（如已指定
   颜色 / 型号 / 数量 / 类型）绝不重复问；每条疑问必须针对题面未给出的关键信息；
   没有疑问时输出空 questions 数组；宁缺毋滥」。

## 测试（tdd 先红）

- test_llm.py：
  - 5000 字符题面 clarify：payload user prompt 含完整题面（无截断标注「内容过长」字样）。
  - 15000 字符题面 clarify：payload user prompt 含前 12000 字符 + 截断标注。
  - CLARIFY_SYSTEM_PROMPT 含「绝不重复问」/「已明确」约束（常量契约断言，参照
    SKELETON_NO_UNUSED_RULE 双端断言先例）。
- 既有测试全绿。

## 验收

- 全量 pytest 绿 + mypy 干净；重启服务后长题面澄清不再问题面已明确的细节。

## 实施记录

- llm.py：新增 CLARIFY_TOPIC_CAP=12000（注释含 wire 账本：72KB + 历史 15KB = 87KB < 128KB）；
  `_clarify_user_prompt` 题面改走 truncate_content(problem_text, CLARIFY_TOPIC_CAP)
  （不再用通用 4000 预算；截断标注保留）；CLARIFY_SYSTEM_PROMPT 加固——「题面已明确给出
  的细节（如已指定颜色、型号、数量、类型）绝不重复问——先逐句核对题面，确认某条信息
  题面确实没有给出才可提问」「宁缺毋滥——题面已覆盖的信息不问、可合理假设的不问」。
- tests/test_llm.py：+3 测试（≤12000 完整保留无标注 / >12000 前 12000 + 截断标注 /
  提示词含「绝不重复问」「已明确」「宁缺毋滥」）；既有 test_clarify_truncates_oversized_problem
  预算常量改引 CLARIFY_TOPIC_CAP（语义不变，4000→12000）；import 补 CLARIFY_TOPIC_CAP。

## 评审记录

- Spec/Standards 双轴 subagent 均长时间未返回被中断（环境卡顿），自查收尾：
  - 验收 1：5000 字符题面完整保留、15000 字符题面前 12000 + 截断标注——test 实证 ✓
  - 验收 2：提示词含「已明确」「绝不重复问」「宁缺毋滥」三约束 ✓
  - 验收 3：全量 2175 passed（+3）、mypy 59 文件干净 ✓
  - wire 账本：12000×6B + 历史 2500×6B = 87KB < 128KB；clarify 不带参考注入无联动冲突 ✓
  - 范围外遵守：_build_user_prompt 未动（select/骨架题面预算不变）✓
  - 提示词新旧句自洽：「题面证据不足以判定时补问」（缺什么问什么）+「题面已明确的不问」
    +「宁缺毋滥」——先核对后提问，语义无冲突。

**收尾备注（2026-xx-xx）：** 本工单完成后未及时标记，顶部状态改 resolved；删除末尾重复的 Status 行（状态字段仅顶部一处）。实现提交：eb39cbd（clarify 题面预算 4000→12000 + 题面已明确细节绝不重复问）。
