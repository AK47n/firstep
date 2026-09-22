# 02 — 资料库更新会话态进 AppContext（check 缓存 + 下载任务单例 + 一把锁）

**要做什么：** 资料库更新的两样会话态（最近一次 check 结果 = apply 的批次白名单来源；进行中
的下载任务单例）从 `webapp` 模块级搬进 `AppContext`，并把「查在跑 → 建任务」这一步用新增的
`_materials_task_lock` 收成原子的。四个端点（check / apply / status / cancel）全部经
`context.*` 读写；`tests/test_materials_task.py` 的 autouse 清扫夹具**删掉**——它的存在理由
（模块级状态跨用例共享）已经消失。

**被谁阻塞：** 无——可立即开始（与 01 改同一个文件，实操按顺序做，避免同文件并发编辑）

**状态：** ready-for-agent

## 验收标准

- [ ] `AppContext` 新增 `materials_last_check: dict` / `materials_task: ApplyTask | None` /
      `_materials_task_lock`；模块级 `_MATERIALS_LAST_CHECK` / `_materials_task` 与那段注释块
      整条退场，`webapp` 的 `global` 语句清零
- [ ] check 端点把结果**就地 update** 进 `context.materials_last_check`（语义不变：仍是 apply
      的批次白名单来源）
- [ ] apply 端点的白名单取源 / 磁盘校验 / 空槽判据 / 任务赋值、status 的读取、cancel 的判据 +
      `cancel()` + 快照落盘全部经 ctx；`_materials_task_lock` 只让「查在跑 → 建并赋任务」与
      「查在跑 → 取消并快照」这两段原子
- [ ] 语义零漂移：apply / status / cancel 的中文文案、状态判据（`downloading` / `applying`）、
      快照路径与落盘时机不变；「进程死 = 任务自然终止、快照落盘可恢复」不变
- [ ] **新增行为判据（收走前是红的）**：两个 app 实例互不可见——A 实例 check 出来的批次对 B
      实例的 apply 不是白名单（B 报「未知批次」400）
- [ ] `tests/test_materials_task.py`：autouse 重置夹具**删除**；注入 check 结果改为在自建 ctx 上
      `ctx.materials_last_check.update(check)`；`_client()` 改返回 `(client, ctx)`（4 处调用点）
- [ ] `tests/test_materials_update.py` 的两条 check 端点用例零改动仍绿（它们只读响应，不碰会话态）
- [ ] `python -m pytest -n auto -q` 全绿
- [ ] 未改动：端点路径与载荷、`updates/` 目录与快照文件名、工具根、前端任何字节

## Comments
