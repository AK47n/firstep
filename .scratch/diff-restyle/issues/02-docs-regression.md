# 工单 02：文档回归（CONTEXT.md + 全量测试）

Status: resolved

## 目标

- CONTEXT.md：任务推进行补「效果 diff 展示 = fx/diff.js（mainDiffHTML / diffStatsLineHTML，主题化行级视图，工单 diff-restyle/01 从 ui/generate-revise.js 迁入）」。
- 全量回归：pytest 全量 + JS 全量 + 语言/README 检查。

## 验收

1. CONTEXT.md 该行含 fx/diff.js 与 diff-restyle/01 标注（已做）。
2. `python -m pytest tests/ -q` 全绿。
3. `node --test tests/js/*.test.mjs` 全绿（552）。
4. git 工作树 src/tests/CONTEXT.md 之外无未跟踪源码改动（.scratch 历史遗留除外）。
