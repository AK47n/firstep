# 僵尸「进行中」恢复（工单 02：文档回归）

Status: resolved

## 交付

1. **CONTEXT.md 任务推进行**：补「僵尸 doing 恢复」词条——`ALLOWED_STATUS_TRANSITIONS` doing→pending（执行中断恢复通道，不做自动清孤儿 / doing→failed）；webapp `_running_task_execs` 进程内注册表（tasks_execute add/discard、tasks_status 占用时 400「正在执行中」）；前端 `taskCardActions(status, opts.recoverable)` doing→["recover"] + `btn-task-recover`「已中断？恢复此步」（仅 !tasks.busy 显示）。
2. 全量回归：pytest（先 Remove-Item Env:FIRSTEP_LAUNCHER + PYTHONPATH=src）+ JS `node --test tests/js/*.test.mjs` + 语言/PS1/CHANGELOG 检查。
3. 中文提交（含本 spec/issues 02；探针不提交）。

## 验收

- 词条与代码一致（doing→pending 单通道、注册表语义、按钮显隐条件）。
- 全量绿；工作树 src/tests/CONTEXT.md 干净。
