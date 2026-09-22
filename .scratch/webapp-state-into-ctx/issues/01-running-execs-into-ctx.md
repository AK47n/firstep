# 01 — 任务执行注册表进 AppContext（每个 app 实例一张）

**要做什么：** 「任务正在执行」这张进程内注册表从 `webapp` 模块级搬进 `AppContext`：
`/api/tasks/execute` 的登记与清理、`/api/tasks/status` 的占用拒绝都经
`context.running_task_execs` 读写；并新增一条行为判据钉住「两个 app 实例互不可见」。
对用户行为零变化（服务的模块级 `app` 只有一份状态）；对测试：不再 import 私有名。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

## 验收标准

- [x] `AppContext` 新增字段 `running_task_execs: set[str]`（形状照 `pending_generations`）；
      模块级 `_running_task_execs` 与它那段注释整条退场
- [x] `/api/tasks/execute` 的 SSE 闭包：登记与 `finally` 清理都走 `context.running_task_execs`
      （完成 / 异常两条路都清）
- [x] `/api/tasks/status` 的占用判据走 `context.running_task_execs`；400 判据与中文文案一字不变
- [x] **新增行为判据（收走前是红的）**：同一进程里两个 app 实例的注册表互不可见——A 实例登记
      `t1` 后，B 实例对 `t1` 的改标端点不拒（200），A 自己照旧拒（400）
- [x] `tests/test_task_progress.py` 的三处 private import 清零：夹具拆成 `tasks_context`
      （返回 `(ctx, holder)`）+ `tasks_client`（依赖前者，返回值仍是 `(client, holder, tmp_path)`），
      既有 30+ 处解包一行不动；三处断言改在 `ctx.running_task_execs` 上做
- [x] 既有判据零削弱：执行注册表三条用例（完成路径已清 / 异常路径已清 / 占用时拒绝）行为不变
- [x] `python -m pytest -n auto -q` 全绿
- [x] 未改动：端点路径与载荷、`webapp` 其余模块级常量、前端任何字节

## Comments

### 2026-09-22 落地读数

- **红 → 绿**：先动测试（夹具拆 `tasks_context` / `tasks_client`、三处 private import 退场、
  新行为判据）→ **4 failed**（全部 `AttributeError: 'AppContext' object has no attribute
  'running_task_execs'`）→ 实现后 `tests/test_task_progress.py` **97 passed**。
- **全量**：`python -m pytest -n auto -q` → **5061 passed + 1 skipped / 162.77s**。
- **行为红证（收走前的读数）**：`.scratch/webapp-state-into-ctx/probe-00-sharing.py` 起两个
  app 实例、按版本自动识别注入缝；读数在 `verify-00-sharing-before.txt`：
  注入缝 = `webapp._running_task_execs`（模块级）→ A 改标 400、**B 改标也 400**（共用同一张
  注册表）；注入缝 = `webapp._MATERIALS_LAST_CHECK`（模块级）→ **B 的 apply 认了 A 的批次 = 200**
  （两边共用白名单）。新用例在收走前只能红在 AttributeError（那时还没有这个缝），
  **行为红由这支探针承担**（已写进用例 docstring）。
- **双轴评审**（固定点 `5c9fc8b0`，两轴各一个并行子代理）：
  - **Standards 轴：0 硬违规**；两条判断题当场修掉——① 抽 `_make_zombie_doing()`
    （「僵尸 doing 前置」原本两条用例逐字重复）；② 新用例去掉被 `tasks_client` 解包覆盖的
    影子 `tmp_path` 夹具参数。另记一条潜在地雷：新字段插在 `hwcheck_recipe_path` **之前**
    会移动位置参数顺序——实测全仓 54 处 `AppContext(...)` 全是关键字传参（AST 扫描过），
    今日不炸。
  - **Spec 轴：无缺失 / 无阻塞**。一条范围蔓延判定为「与工单 04 的 grep 口径一致、可接受」：
    `tasks_status` docstring 里的名字同批改新（同一份源码里的事实）；另一条记录级建议已采纳
    （新用例 docstring 注明行为红证来源）。
