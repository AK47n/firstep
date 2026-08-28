# 工单 03：灵活修正文档回归（CONTEXT.md + 全量）

Status: resolved

## 目标

- CONTEXT.md：任务推进行补「灵活修正」词条（/api/tasks/idea/*、IdeaAnalysis、needs_redo、run_direct_fix、EVENT_IDEA_ANALYZING、fx/task.js 新函数）；「步骤报告」行如涉及受影响标记同步。
- 全量回归：pytest 全量 + JS 全量 + 语言/CHANGELOG 检查。

## 验收

1. CONTEXT.md 含 idea-fix 词条（入口 / 三分类 / 落地按钮 / needs_redo 联动 / 范围外排期）。
2. pytest 全量绿；JS 全量绿；test_repo_language / test_changelog / test_ps1_encoding 绿。
3. 工作树 src/tests/CONTEXT.md 之外无未提交源码改动。
