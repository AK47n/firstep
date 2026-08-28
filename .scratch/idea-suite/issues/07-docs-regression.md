# 工单 07：文档回归（CONTEXT.md + 全量测试）

Status: resolved

## 目标

实现 spec 收尾：CONTEXT.md 词条补齐 idea-suite 三项功能；全量回归验证。

## 交付

- CONTEXT.md：「任务推进」域补 idea-suite 三词条行——全局工程级商量（idea_chat.py / `.contest_idea_chat.json` / note 全局结论注入 execute/run_direct_fix 的 global_note / EVENT_IDEA_CHAT / discuss_global_idea）、清单微编辑（update_task_fields / move_task / `/api/tasks/idea/edit|move`）、草稿箱（drafts.py / `.contest_ideas.json` / 三端点 / 去重）；新 fx 名（globalChatHTML / globalNoteBadgeHTML / taskEditFormHTML / taskMoveButtonsHTML / ideaDraftListHTML）与修复记录（如 .bak 先校验后备份、backup 是 move 语义）。
- 全量回归：pytest（**不带 FIRSTSTEP_LAUNCHER**；基线 2670 + 新增）全绿；JS `node --test tests/js/*.test.mjs` 全绿；语言/PS1 编码 / README / CHANGELOG 检查全绿。
- 提交：中文提交信息（含 spec + issues 随提；探针/日志不提交）。

## 验收

1. CONTEXT.md 词条与代码一致（新后端模块/端点/文件名/事件/fx 导出都在词条内）。
2. 全量 pytest 绿；JS 全量绿；语言检查绿。
3. git 历史干净：idea-suite 相关提交链完整，工作树 src/tests/CONTEXT.md 干净。
