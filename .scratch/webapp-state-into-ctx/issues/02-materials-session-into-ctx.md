# 02 — 资料库更新会话态进 AppContext（check 缓存 + 下载任务单例 + 一把锁）

**要做什么：** 资料库更新的两样会话态（最近一次 check 结果 = apply 的批次白名单来源；进行中
的下载任务单例）从 `webapp` 模块级搬进 `AppContext`，并把「查在跑 → 建任务」这一步用新增的
`_materials_task_lock` 收成原子的。四个端点（check / apply / status / cancel）全部经
`context.*` 读写；`tests/test_materials_task.py` 的 autouse 清扫夹具**删掉**——它的存在理由
（模块级状态跨用例共享）已经消失。

**被谁阻塞：** 无——可立即开始（与 01 改同一个文件，实操按顺序做，避免同文件并发编辑）

**状态：** resolved

## 验收标准

- [x] `AppContext` 新增 `materials_last_check: dict` / `materials_task: ApplyTask | None` /
      `_materials_task_lock`；模块级 `_MATERIALS_LAST_CHECK` / `_materials_task` 与那段注释块
      整条退场，`webapp` 的 `global` 语句清零（实测 0 处）
- [x] check 端点把结果**就地 update** 进 `context.materials_last_check`（语义不变：仍是 apply
      的批次白名单来源）
- [x] apply 端点的白名单取源 / 磁盘校验 / 空槽判据 / 任务赋值、status 的读取、cancel 的判据 +
      `cancel()` + 快照落盘全部经 ctx；`_materials_task_lock` 只让「查在跑 → 建并赋任务」与
      「查在跑 → 取消并快照」这两段原子
- [x] 语义零漂移：apply / status / cancel 的中文文案、状态判据（`downloading` / `applying`）、
      快照路径与落盘时机不变；「进程死 = 任务自然终止、快照落盘可恢复」不变
- [x] **新增行为判据（收走前是红的）**：两个 app 实例互不可见——A 实例 check 出来的批次对 B
      实例的 apply 不是白名单（B 报「未知批次」400）
- [x] `tests/test_materials_task.py`：autouse 重置夹具**删除**；注入 check 结果改为在自建 ctx 上
      `ctx.materials_last_check.update(check)`；`_client()` 改返回 `(client, ctx)`（4 处调用点）
- [x] `tests/test_materials_update.py` 的两条 check 端点用例零改动仍绿（它们只读响应，不碰会话态）
- [x] `python -m pytest -n auto -q` 全绿
- [x] 未改动：端点路径与载荷、`updates/` 目录与快照文件名、工具根、前端任何字节

## Comments

### 2026-09-22 落地读数

- **红 → 绿**：先动测试（删 autouse 清扫夹具、`_client()` 返回 `(client, ctx)`、注入改走自建
  ctx、新增两条行为判据）→ **2 failed**（`AttributeError: 'AppContext' object has no attribute
  'materials_last_check'`）→ 实现后 `tests/test_materials_task.py` + `tests/test_materials_update.py`
  = **34 passed**。
- **全量**：`python -m pytest -n auto -q` → **5063 passed + 1 skipped / 128.19s**（比 01 多出的
  2 条 = 本单两条行为判据）。
- **探针对读**（`probe-00-sharing.py`，同一支探针改动前后各跑一次）：
  `verify-00-sharing-before.txt` —— 注入缝 = `webapp._MATERIALS_LAST_CHECK`（模块级）→
  **B 的 apply 认了 A 的批次 = 200**；`verify-00-sharing-after.txt` —— 注入缝 =
  `ctx.materials_last_check` → **B 的 apply 不认 = 400**（A 自己仍认，判据没变）。
- **双轴评审**（固定点 `3a360fda`，两轴各一个并行子代理）：
  - **Spec 轴抓到一条真问题（已修）**：我把「查在跑 → 400」连同建清单一起挪进了锁，判定次序
    于是从「磁盘校验 → 查在跑 → 建清单」变成「磁盘校验 → 建清单 → 查在跑」——同一请求
    「有任务在跑 **且** 本地基线清单读不出来」时答复会从「已有资料库更新任务在进行中」变成
    清单那个错。**修法**：把这一整段（查在跑 + 建清单 + 建任务 + 占槽）整段留在**原位**、
    一起进锁，语句次序逐字回到收走前（提交前已复核 diff）。
  - **Spec 轴另一条（范围蔓延，已回退）**：我顺手把两处「在跑」判据收成
    `_MATERIALS_RUNNING_STATES` + `_materials_task_running()`，spec 未授权此重构 → **回退**成
    按原文字面量内联（只加 `context.` 前缀），`TaskState` / `TypeGuard` 两个新 import 一并撤掉。
  - **Standards 轴 0 硬违规**；四条判断题里两条按建议修（AppContext 注释补明「**归属在 ctx =
    每个 app 实例一份**」，与 01 的 `running_task_execs` 同形；测试里的 check 注入形状抽成
    `_seed_check()` 单源），两条**记录不改**：full-task 侧同类字面量属完整包链路（spec 范围外）；
    两个用例文件各自的 `_client` 是既有形状，合并会让两个测试文件互相耦合。
  - 两条「既不修也如实记账」的既存事实：① `materials_last_check` 的读—改—写无锁（收走前同样
    没有，本单不新增锁语义）；② cancel 锁内写快照（几 KB、不重入任何锁，无死锁面）——把
    「查在跑 → 取消并快照」整段放进锁是为了与 apply 的占槽互斥。
  - **超字面要求但保留的一条**（`test_check_then_apply_keeps_the_whitelist_on_this_instance`）：
    它补的是此前**完全没有覆盖**的缝——改动前 check → apply 的真实链路一条用例都没有（apply
    的白名单全靠 monkeypatch 模块全局注入）。工单只说「新增一条行为判据」，这一条与
    `test_two_app_instances_do_not_share_the_batch_whitelist` 合起来才把「A 实例 check 出来的
    批次对 B 不可见 + 本实例内闭环」两面都钉住，故保留（评审也认它补上了那条链路）。
