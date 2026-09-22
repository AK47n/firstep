# 01 — 完整包会话态进 AppContext（check 缓存 + 任务单例 + 四个 accessor 退场）

**要做什么：** 完整包（一键全量更新）链路的模块级会话态从 `full_task` 搬进 `AppContext`：
最近一次 check 结果（=`apply` 的分卷白名单来源）与进行中的下载任务单例，四个端点
（check / apply / status / cancel）与 `_full_apply_complete` 全部经 `context.*` 读写；
`full_task.py` 的四个 accessor（`get_full_task` / `set_full_task` / `last_check` /
`set_last_check`）整条退场。测试换缝：在自己构造的那个 ctx 上注入与断言，两份 autouse
清扫夹具删除；并新增两条「两个 app 实例互不可见」的行为判据（收走前是红的）。

对用户行为零变化（跑着的服务里只有一个 app 实例，状态本来就只有一份）。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

## 验收标准

- [x] `AppContext` 新增 `full_last_check: dict` / `full_task: FullDownloadTask | None`（形状照
      `materials_last_check` / `materials_task`——缝外的状态公开、缝内的互斥件私有）；
      `full_task` 模块级的 `_LAST_CHECK` / `_FULL_TASK` 与那段注释块整条退场，该模块 `global`
      语句清零（收走前**实测全 `src/` 仅剩这一处**；收走后 `src/` 全域 `global` = 0）
- [x] 四个 accessor 删除，**不留兼容别名**（引用面已量：`webapp` 8 处 + 三个测试文件；收走后
      全仓只剩注释里的历史说明）
- [x] check 端点把结果**先 `clear()` 再 `update()`** 写进 `context.full_last_check`（就地写，
      语义与收走前逐字相同——**不是**资料库那半的裸 `update`；统一两者就是改语义，不在本条）
- [x] apply 的白名单取源 / 兜底自查后的重写 / 磁盘校验 / 查在跑 / dry_run 早返 / 建任务 /
      占槽、status 的读取、cancel 的判据 + `cancel()` + 强制快照全部经 ctx；**语句次序与中文
      文案逐字不变**（判定次序也是判据）
- [x] `_full_apply_complete`（后台线程）仍在**任务完成那一刻**读 `context.full_last_check`
      取 `latest_version` / `manifest_url`——不许在登记回调时把它捕获成局部变量
- [x] **新增行为判据（收走前是红的）**：两个 app 实例互不可见——① A 实例 check 出来的分卷对
      B 的 apply 不是白名单（B 走兜底自查后 400），A 自己用它照旧 200；② A 实例登记的
      「正在下载」对 B 的 apply 不可见（B 不被拒），A 自己照样 400「已有完整包下载任务在进行中」
- [x] `tests/test_full_task.py`：`_client()` 改返回 `(client, ctx)`（9 处调用点）、`_seed_check()`
      改成在自己的 ctx 上写、autouse 清扫夹具**删除**、三处 `ft._FULL_TASK = …` 与一处
      `ft.get_full_task()` 改经 ctx
- [x] `tests/test_full_apply.py`：autouse 夹具删除、两处内联构造的 app 保留 ctx、两处
      `ft.set_last_check(...)` 改经 ctx；`tests/test_download_status_surface.py`：一处
      `ft.set_full_task(None)` 改经 ctx
- [x] 既有判据零削弱：状态空态 / 未知分卷 400 / 演练不登记任务 / 在跑拒 apply / 无任务取消空转
      等行为一字不变（只换「取状态的姿势」）
- [x] 前后对读探针落 `.scratch/full-update-state-into-ctx/probe-00-*.py`：同一支探针改动前后
      各跑一次（模块级缝 → B 认 A 的白名单与任务槽；ctx 缝 → 不认），读数落盘
- [x] `python -m pytest -n auto -q` 全绿；`node --test "tests/js/*.test.mjs"` 全绿
- [x] 未改动：端点路径与载荷、快照文件名与路径、工具根、前端任何字节、`create_app()` 与模块级 `app`

## Comments

### 2026-09-22 19:3x 落地读数

- **红 → 绿**：先换测试缝 + 加两条行为判据（此时 `AppContext` 上还没有那两个字段）→ 三个文件
  **14 failed**（全是 `AttributeError: 'AppContext' object has no attribute 'full_last_check'`）
  → 实现后**全绿**：`tests/test_full_task.py` + `test_full_apply.py` +
  `test_download_status_surface.py` + `test_full_update.py` + `test_update_check.py` =
  **111 passed**（修完评审两条后三文件复跑 74 passed）。
- **行为红证（收走前的读数由探针承担，用例那时只能红在 AttributeError）**：
  `probe-00-sharing.py` 同一支探针改动前后各跑一次，读数
  `verify-00-sharing-before.txt` / `-after.txt` 直接对读——
  - ① 白名单：注入缝 `full_task._LAST_CHECK`（模块级）→ **B 认了 A 的分卷 = 200**；
    改成 `ctx.full_last_check` 后 → **B 不认 = 400**（答复 = 兜底自查桩那句 message），
    A 自己两轮都 200；
  - ② 任务槽：注入缝 `full_task._FULL_TASK`（模块级）→ **B 跟着拒 = 400**；
    改成 `ctx.full_task` 后 → **B 看不见 = 200**，A 自己两轮都 400，且 B 的 apply 不动 A 的槽位。
  - 探针自身的一处判据污染当场修掉：旧形状下 A 的 apply 会在**共享**任务槽里留下任务，
    B 那一格于是拒在「已有任务在跑」而不是白名单上（读数是 400 却不是因为白名单）——
    现在这一格先清槽，判据只落在白名单上。
- **全量**：`python -m pytest -n auto -q` → **5072 passed + 1 skipped / 136.06s**
  （C6 收尾 5070 ＋ 本条两条行为判据 ＝ 5072）。
  ⚠ 另一次复跑出现 **1 failed**＝`tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest`
  ——**是本仓已记录的并行争用偶发**（那条用例在 `--full` 路径上真跑整支浏览器门禁）：
  该文件单跑 **29 passed / 78.05s**（与 `docs/agents/local-environment.md` 记的读数同数），
  随后的整支复跑 5072 全绿。与本次改动无关，按既有口径记账。
- **前端门禁**：`node --test "tests/js/*.test.mjs"` → **1702 passed / 0 fail**（与 C6 收尾同数；
  本条前端零字节改动，属回归确认）。
- **双轴评审**（固定点 = `c6040566`，改动当时未提交，两轴各一个并行子代理跑工作树 diff）：
  - **Standards 轴：0 硬违规**。三条判断题：① `clear()+update()` 现在两处（收走前单源在
    `set_last_check` 里）——spec 明禁顺手抽 helper，**记为代价不判违规**；② 两处
    `("downloading","applying")` 字面重复是既有，同样不抽；③ 新用例直接断言 `ctx.full_task`
    槽位，比 C6 先例多走一步——**保留**：ctx 字段是 spec 声明的「缝外公开」缝，且
    `assert ctx.full_task is None` 与收走前那条 `ft.get_full_task() is None` 是 1:1 的换缝，
    另两条钉的是「B 的 apply 不动 A 的槽位」这条本条的核心事实。
  - **Spec 轴：无缺失**（12 条验收逐条 landed；六点抽查全过：判定次序与文案逐字未变、仍
    clear+update、后台线程仍在完成那刻读、四 accessor 零残留无垫片、`_client()` 9 处全改、
    探针读数与工单原文一致）。范围蔓延两条：`FullDownloadTask` 类 docstring 那句「webapp
    模块级单例」在删掉模块状态的那一刻就成了假话，**随本条一起改对**（工单 04 的同名条目
    因此已提前完成，见下）；`test_download_status_surface.py` 多出的
    `assert ctx.full_task is None` 是加强不是削弱，保留。
  - 两条可疑项**都采纳并修**：① `test_full_apply.py` 两处注入补上 `clear()`，与生产写入形状
    及 `_seed_check()` 单源一致；② 新判据①的断言从「含『完整包』」收紧成**钉住兜底自查桩那
    句 message**（否则分不清「自查回来没有」与「暂无可用的完整包信息」，判别力会掉到只剩状态码）。
- **顺带记账（工单 04 的条目提前做掉一条）**：`full_task.py` 的两处「webapp 模块级单例」话术
  （模块级那段注释块 + 类 docstring）已随本条改对；工单 04 那边**只剩** `CONTEXT.md` 词条、
  `backlog.md`、`local-environment.md` 三件。
- **未跑真机**：本轮不起服务器、不跑 `drill-04`（spec 已定：验收深度 = 测试门禁）。
