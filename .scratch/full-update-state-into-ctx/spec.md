# spec — 完整包链路的会话态进 AppContext（full-update-state-into-ctx）

## 问题陈述

C6（`.scratch/webapp-state-into-ctx/`）把 `webapp` 里三样进程级会话态收进了 `AppContext`，
但**完整包（一键全量更新）那条链路的会话态没动**——它的「不做」段原文写着「完整包那一路的
模块级会话态（`full_update` 的 check 缓存 / `full_task` 的当前任务）不动——本条只收这三样」。
于是同一个更新功能的两半**两种形状**：资料库那半经 `context.*` 读状态，完整包这半仍挂在
`full_task` 模块级，还包着四个 accessor（`get_full_task` / `set_full_task` / `last_check` /
`set_last_check`）。

遗留的症状三层（与 C6 同款）：

- **「每个 app 实例一份状态」是假的**：同一个进程里两个 `create_app(...)` 实例**共用**一份
  check 缓存与同一个任务槽。A 实例 check 出来的分卷，B 实例的 apply 照样当白名单用；
  A 实例登记为「正在下载」的任务，B 实例的 apply 照样被拒。
- **测试只能跨缝**：三处直改私有名（`ft._FULL_TASK = …`）、一处直改 `ft._LAST_CHECK`，
  外加**两份 autouse 清扫夹具**（`tests/test_full_task.py` 与 `tests/test_full_apply.py`
  各一份，共 6 次 set 调用）在每个用例前后把模块全局抹干净。那夹具是**事后清扫**：它压住的是
  「上一个用例留下的状态」，而不是让状态从一开始就不该被共享。
- **`global` 语句**：`full_task.py` 一处——实测**这是整个 `src/` 里仅剩的一处**（C6 已把
  `webapp` 的三处清零）。「进程级状态」这种形状只剩这最后一个入口能写进去。

**另有一条真竞态（这轮唯一用户可见的一面）**：apply 端点的「查在跑 → 建任务 → 占槽」是
check-then-act，同步端点跑在线程池 worker 上，中间还夹着下载任务的构造（**要读磁盘快照**，
窗口很宽）。两个并发 apply 能同时通过检查：第二个静默顶掉第一个的槽位——那个任务还在跑、
却再也查不到 / 取消不了；两个线程还往**同一个 `updates/full/` 目录、同一批卷**里写，快照也是
两份。前端（`ui/full-update.js` 的 `startDownload` 与**重试按钮**）没有防重，两个标签页即可
触发。C6 给资料库那半补锁修的就是**同一个缺陷**，当时没顺手带到这半。

来源：C6 spec 的「不做」段 + `.scratch/backlog.md` §17 末尾「剩余」（原话是 C7 只是验收尺、
未立项——也就是说 C6 的这条尾巴是架构评审候选里最后的挂账项）。

## 方案

把这两样状态的**归属**搬进 `AppContext`，四个端点（check / apply / status / cancel）与
相关 helper 一律经 `context.*` 读写；测试与调用方走**同一条缝**——测试在**自己构造的那个
ctx** 上注入与断言，不再伸手进模块。语义一字不改：

- `full_last_check` 仍是「最近一次 check 结果 = apply 的分卷白名单来源」；
- `full_task` 仍是「进行中的下载任务单例（进程死 = 任务自然终止，快照落盘可恢复）」。

随搬家补齐 C6 已有的那把锁：`_full_task_lock`——只让 apply 的「查在跑 → 建任务 → 占槽」与
cancel 的「查在跑 → 取消 + 快照」这两段 check-then-act 原子。**只让这两步原子，判据与文案
一字不改**，语句次序逐字留在原位（判定次序也是判据）。

对用户：**行为零变化**（除并发竞态被修掉）。模块级 `app = create_app()` 照旧可用（uvicorn
入口 `contest_generator.webapp:app`），跑着的服务里这两样状态本来就只有一份。

## 用户故事

1. 作为维护者，我想让完整包链路的会话态长在 `AppContext` 上，以便同一功能的更新链路两半
   同形，DI 缝不再半开。
2. 作为维护者，我想让 `src/` 全域 `global` 语句归零，以便「进程级状态」这种形状在闸门内就
   写不进去。
3. 作为维护者，我想让那四个 accessor 整条退场（不留兼容别名），以便状态的归属不再有第二种
   说法。
4. 作为测试作者，我想在自己构造的 ctx 上注入 check 结果与任务槽，以便不再直改
   `_FULL_TASK` / `_LAST_CHECK` 这种私有名。
5. 作为测试作者，我想让两份 autouse 清扫夹具退场，以便每个用例天然隔离（两个 app 实例互不
   可见），新写的用例不必抄夹具、也不怕被邻居污染。
6. 作为用户，我想让双击「开始下载」或开两个标签页不会起出两个并发完整包下载（写同一批
   文件），以便不会下出一份谁也说不清的坏包。
7. 作为用户，我想让 check / apply / status / cancel 的文案、状态机、快照与卷级续传行为一字
   不变，以便感觉不到这次改动（除了竞态被修掉）。
8. 作为评审，我想让这次改动**只有两个动作**（换归属、补一把锁），判定次序与字面量逐字留在
   原位，以便能逐行对账。

## 实现决策

- **归属**：两样状态成为 `AppContext` 的字段（形状照 `materials_last_check` / `materials_task`
  ——缝外的状态公开、缝内的互斥件私有）：`full_last_check: dict` / `full_task:
  FullDownloadTask | None`；外加 `_full_task_lock`（只在 apply / cancel 两处的 check-then-act
  上用）。命名与资料库那半对称（`materials_*` ↔ `full_*`）。
- **四个 accessor 整条退场**：`get_full_task` / `set_full_task` / `last_check` / `set_last_check`
  删除，不留兼容别名。全仓引用面已量过：`webapp` 8 处 + 三个测试文件。
- **check 写入的形状照抄不改语义**：仍是**先 `clear()` 再 `update()`** 的就地写（不是资料库
  那半的裸 `update`）——两者语义确实不同（旧的 check 里消失的键，比如 `manifest_url`，必须
  跟着消失），**统一它们就是改语义**，不在本条。
- **后台线程晚读**：`_full_apply_complete` 在任务完成那一刻才读 check 结果（取
  `latest_version` / `manifest_url`）。搬家的读侧必须仍在**那一刻**读 `context.full_last_check`，
  不许在登记回调时把它捕获成局部变量。
- **锁覆盖哪两段、语句次序逐字留在原位**：
  - apply：`磁盘校验 → 查在跑 → dry_run 早返 → 建任务 → 占槽 → 起线程`——「查在跑 → 建任务 →
    占槽 → 起线程」进锁；**兜底自查那份网络调用（`_refresh_check`）留在锁外**。
    **spec 修订（2026-09-22，双轴评审提出后经用户追认）**：起线程那一句也进锁——**比资料库那半
    宽一条语句**（那半的 `worker.start()` 留在锁外）。理由：占槽之后、`run()` 把状态置成
    downloading 之前任务仍是 IDLE，那一跳若被第二个请求读到，它照样会放行；`Thread.start()`
    本身等到新线程真的跑起来才返回（不做 I/O、不阻塞），于是那道缝从「整段构造（要读断点
    快照）」缩到「线程调度一跳」。**这是收紧，不是硬保证**——无懈可击的写法是把判据从
    「状态在跑」改成「槽位被占」，那是改语义，明确不在本条；资料库那半留着同一条缝，
    本轮不动（两半跨度的差异连同理由一起记账）。
  - cancel：`查在跑 → 取消 → 强制快照`整段进锁（与 apply 的占槽互斥）。
- **不做**（C6 评审实证过的两条纪律）：不许顺手把两处「在跑」判据抽成常量 / helper（C6 那次
  被 Spec 轴判成范围蔓延并回退）；不许顺手把 `_client` 之类的夹具与别的测试文件合并。
- **不动**：端点路径 / 载荷形状 / 中文文案 / 状态机（`downloading` / `applying`）/ 快照路径与
  文件名 / 工具根 / 前端任何字节（本轮预计**前端零字节变更**）/ `create_app()` 与模块级 `app`。
- **范围外（写死，防蔓延）**：`src/` 里另外三处模块级可变容器——`materials_pack` 的
  `_EXTRA_DIR_SLUGS`、`syscfg_instances` 的 `INSTANCES_BY_SLUG`、`vision` 的
  `_IMAGE_DESCRIBE_CACHE`——它们是**按内容键的进程级缓存 / 派生常量表，不是会话态**：收进 ctx
  会让每个实例重算（`vision` 那个还会重复打 LLM），判据面也不同。tests 里三处常量注册表同理。

## 测试决策

- **回归网 = 既有测试**，断言一字不改，只改「取状态的姿势」：`tests/test_full_task.py`（全量）、
  `tests/test_full_apply.py`、`tests/test_full_update.py` 与 `tests/test_download_status_surface.py`
  的端点用例。
- **测试换缝**（先例 = C6 的 `tests/test_materials_task.py`；同一把钥匙：夹具把自己构造的 ctx
  交出来）：
  - `tests/test_full_task.py` 的 `_client()` 改成返回 `(client, ctx)`（9 处调用点）；
    `_seed_check()` 改成在自己的 ctx 上写 `ctx.full_last_check`；autouse 清扫夹具**删掉**；
    三处 `ft._FULL_TASK = …` 与一处 `ft.get_full_task()` 改成经 ctx。
  - `tests/test_full_apply.py`：autouse 夹具删掉；两处内联构造的 app 保留 ctx；两处
    `ft.set_last_check(...)` 改成 ctx。
  - `tests/test_download_status_surface.py`：一处 `ft.set_full_task(None)` 改成 ctx。
- **两条新的行为判据（收走前是红的，这是本条的卖点）**：两个 app 实例互不可见——
  ① A 实例 check 出来的分卷不是 B 的 apply 白名单（B 走兜底自查 → 400），A 自己用它照旧 200；
  ② A 实例登记的「正在下载」对 B 的 apply 不可见（B 不被拒），A 自己照样 400
  「已有完整包下载任务在进行中」。先例 = C6 的两条同款判据（真 TestClient + 桩 check / 桩下载器）。
- **锁的判据**：一条**真并发**用例（**同一个 app 的一个 client ＋ 两个线程**；「两个 `TestClient`
  指向同一个 ctx」的等价形状，修前红实测证明这个 client 不做串行化），用事件把第一个请求卡在
  临界区内再放第二个——修前第二个请求能同时过关（200）、两个任务被建出来，修后它必须等锁并
  吃到 400，且槽位仍是第一个任务。**诚实记账**：用例里 `start_full_update` 的桩**同步**把状态
  置成 downloading（真实现是起线程、由 `run()` 置），所以这条绿是**按设计构造出来**的，它钉的
  是「查 → 占 → 起线程」这段的原子性；生产里剩下的余量 = 线程启动延迟（见实现决策的 spec 修订）。
  若实测证明它在并行负载下不稳，退路是「注入式」判据 + 结构钉 + 评审见证，并**如实记账**。
- **结构钉扩面**（`tests/test_webapp_state_home.py`，判据是纯函数、源码进事实出）：把现有规则
  **参数化**（模块路径 + 模块对象名 + 搬走的名单 + 正向字段），同一份规则跑**两条腿**
  （`webapp` 照旧、`full_task` 新增），并新增一条 `src/` 全域的腿：**`global` 语句 = 0**。
  C6 的红证探针**不改**（仍喂 `webapp` 那一腿）。
- **红证三件**（沿用 C6 的工具形状，都在 `.scratch/full-update-state-into-ctx/`）：
  ① 前后对读探针（同一支探针改动前后各跑一次：注入缝 = 模块级 → B 认 A 的白名单与任务槽；
  注入缝 = ctx → 不认）；
  ② 真红证（**显式钉收走前那个提交**，不写 HEAD——提交之后 HEAD 就是新代码，红证会静默变绿；
  探针与守卫**共用**同一份聚合判据）；
  ③ 判据强度探针（逐条腿 stub → 变红；**它会真改库内文件、跑完逐字节复原——别和测试套件同时跑**）。
- **全绿**：`python -m pytest -n auto -q` 全绿；`node --test "tests/js/*.test.mjs"` 全绿
  （前端零字节改动，属回归确认）。

## 范围外

- 把模块级 `app = create_app()` 撤走（uvicorn 入口契约，硬约束）。
- 上面点名的三处**进程级缓存 / 派生常量表**（不是会话态，收进 ctx 是错的）。
- 资料库那半与完整包这半在 check 写入形状上的差异（`update` vs `clear+update`）**统一**。
- 前端给「开始下载 / 重试」补防重（后端那把锁是本条的范围，前端防重是另一件事）。
- C7「73 个私有符号被测试翻墙」——当验收尺用，本条不碰。
- 顺手重构（抽常量 / 抽 helper / 合并测试夹具 / 改工具根与快照路径）。

## 补充说明

- **为什么"同一形状"不等于逐字照抄**（两处真实形状差异，也是这轮不等于复制粘贴的原因）：
  ① 状态**不在 `webapp` 里**，而在 `full_task.py`，还包着四个 accessor；② 现有结构钉的判据面
  只认 `webapp` 模块，新落点要求把规则参数化（判据保持单源，探针不受影响）。
- **如实记账、本条不修**的两条既有事实（与 C6 同款）：① check 结果的读—改—写无锁（收走前
  同样没有，本单不新增锁语义）；② cancel 在锁内写快照（几 KB、不重入任何锁，无死锁面）。
- **三条最容易踩的坑**（都是 C6 实证过的）：判定次序被"顺手"改变（Spec 轴抓到过一次真问题）；
  `clear()+update()` 被统一掉（= 改语义）；后台线程晚读被提前捕获（= 取到过期版本号）。
- **三处会变假的旧话术**（随最后一单改）：`full_task.py` 的两处「webapp 模块级单例」注释与
  `set_full_task` 的 docstring「状态单源在本模块」；`CONTEXT.md` 的一键全量下载词条
  （照 C6 给任务推进词条补 `AppContext.running_task_execs` 的同款写法，补明状态归属）。
- `docs/agents/local-environment.md` 按既有惯例补一行本轮会话事实（本轮不起服务器、读数），
  第 0 节的发布落差表不动；`backlog.md` 新增一节记这轮落地账（C6 的尾巴就此结清）。
- 判据口径：本条的验收不是「引用行数变少」，而是**模块级不再有那两样 + accessor 退场 +
  `src/` 全域 `global` 归零 + 既有判据零削弱 + 两条"实例互不可见"能被测出来 + 并发 apply 只放
  一个任务进闸**。
- 验收深度（已定）：**测试门禁即可**——`pytest -n auto` + 前端门禁 + 三件红证探针；本轮不跑
  真机演练（`drill-04` 的 `--recheck` 可随时对已跑完的目录复算，本轮不占用）。
