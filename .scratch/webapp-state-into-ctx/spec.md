# spec — 三个进程级可变状态搬进 AppContext（webapp-state-into-ctx）

## 问题陈述

`webapp` 把三样**会话态**挂在模块级：任务执行注册表（`_running_task_execs`）、资料库
check 结果缓存（`_MATERIALS_LAST_CHECK`）、进行中的资料库下载任务（`_materials_task`）。
症状有三层：

- **「每个 app 实例一份状态」是假的**：同一个进程里 `create_app(不同的 AppContext)` 出来的
  两个实例**共用**这三样（DI 缝 `AppContext` 早就有了，真正有状态的东西却在缝外面）。用例里
  「每个用例建一个 AppContext」的隔离意图只在纸面上成立——A 实例检查出来的批次白名单，
  B 实例的 apply 照样认；A 实例里登记为「正在执行」的任务，B 实例的改标端点照样拒。
- **测试只能跨过 interface**：三处 `from …webapp import _running_task_execs`、一处
  `monkeypatch.setattr(webapp, "_MATERIALS_LAST_CHECK", …)`，外加一个 autouse 夹具在每个
  用例之后把两个模块全局清掉。那夹具是**事后清扫**：它压住的是「上一个用例留下的状态」，
  而不是让状态从一开始就不该被共享。
- **`global` 语句 3 处**（实测），是归属错位的直接症状：函数得显式声明「我要改模块里的东西」。

来源：架构评审报告的 C6（副本入库
`.scratch/ui-dom-contract-gate/architecture-review-20260920-1745.html`）；`backlog.md`
第 11 节末与第 15 节末都记着「仍挂账、未立项」。

## 方案

把这三样状态的**归属**搬进 `AppContext`（有状态的东西跟着实例走），端点与相关 helper 一律
经 `context.*` 读写；测试与调用方走**同一条缝**——测试在**自己构造的那个 ctx** 上注入与断言，
不再伸手进模块。语义一字不改：

- `running_task_execs` 仍是「任务执行互斥（防僵尸恢复）」；
- `materials_last_check` 仍是「最近一次 check 结果 = apply 的批次白名单来源」；
- `materials_task` 仍是「进行中的下载任务单例（进程死 = 任务自然终止，快照落盘可恢复）」。

另加一把锁：`materials_task` 的「查在跑 → 建任务」是 check-then-act（FastAPI 的同步端点跑在
线程池 worker 上，两个并发 apply 能同时通过检查），随搬家补 `_materials_task_lock`（形状照既有
`_generation_lock`）——**只让这一步原子，判据与文案一字不改**。

对用户：**行为零变化**。模块级 `app = create_app()` 照旧可用（uvicorn 入口
`contest_generator.webapp:app`），跑着的服务里这三样状态本来就只有一份。

## 用户故事

1. 作为维护者，我想让「app 的会话态」长在 `AppContext` 上，以便 DI 缝不再漏风。
2. 作为测试作者，我想在自己构造的 ctx 上注入与断言，以便不再 import 私有名、不再 monkeypatch
   模块全局。
3. 作为测试作者，我想让每个用例天然隔离（两个 app 实例互不可见），以便新写的用例不必抄一个
   autouse 清扫夹具，也不怕被邻居用例污染。
4. 作为维护者，我想让 `webapp` 模块级不再有可变全局与 `global` 语句，以便「进程级状态」这种
   形状在闸门内就写不进去。
5. 作为维护者，我想原样保留这三样状态的既有判据（互斥 / 白名单 / 单例），以便这次只换归属、
   不换语义。
6. 作为用户，我想让资料库更新与任务推进两个入口的提示与行为一字不变，以便感觉不到这次改动。

## 实现决策

- **归属**：三样状态成为 `AppContext` 的字段（去下划线，形状照 `pending_generations` /
  `tab_registry`）：`running_task_execs` / `materials_last_check` / `materials_task`；外加
  `_materials_task_lock`（只在 apply / status / cancel 三处的 check-then-act 上用）。
- **不留兼容别名**：模块级那三个名字**整条退场**（结构钉就要求它不在）。全仓引用面已经量过：
  只有 `webapp` 自己 + 两个测试文件（+ 三处会变假的旧名字引用，见最后一单）。
- **测试换缝**：
  - `tests/test_task_progress.py` 的夹具拆成 `tasks_context`（返回 `(ctx, holder)`）+
    `tasks_client`（依赖前者，返回值仍是 `(client, holder, tmp_path)`）——照 `tests/test_webapp.py`
    既有的 `context` / `client` 先例；**30+ 处既有解包一行不动**，只有 3 处受影响用例多收一个
    夹具参数，断言改在 `ctx.running_task_execs` 上做。
  - `tests/test_materials_task.py` 的 `_client()` 改成返回 `(client, ctx)`（4 处调用点）；autouse
    重置夹具**删掉**；原先注入 check 结果的那一处改成在自建 ctx 上
    `ctx.materials_last_check.update(check)`。
- **两条新的行为判据（收走前是红的，这是本条的卖点）**：两个 app 实例互不可见——
  ① A 实例 check 出来的批次对 B 的 apply 不是白名单（B 报「未知批次」）；
  ② A 实例登记的「正在执行」对 B 的改标端点不可见（B 不拒），而 A 自己照样拒。
- **不动**：端点路径 / 载荷形状 / 中文文案 / 快照路径与文件名 / 工具根 / 前端任何行为
  （前端只改 `static/js/fx/task.js` 里一行注释的名字）。
- **不做**（评审同一段提过、但本条范围外）：`app = create_app()` 不从模块顶层撤走（硬约束：
  uvicorn 入口就是它）；完整包那一路的模块级会话态（`full_update` 的 check 缓存 /
  `full_task` 的当前任务）不动——本条只收这三样。

## 测试决策

- **回归网 = 既有测试**：`tests/test_task_progress.py`（执行注册表三条）、
  `tests/test_materials_task.py`（20 条）、`tests/test_materials_update.py` 的 check 端点用例
  ——断言不改（只改「取状态」的姿势）。
- **新增两条行为判据**（见上）：钉住「每个 app 实例拥有自己的状态」这条**外部行为**，
  先例 = 既有端点用例（真 TestClient + 假 LLM / 假下载器）。
- **新增结构钉** `tests/test_webapp_state_home.py`（先例 `tests/test_release_channel_home.py` 与
  `tests/test_hwcheck_assembly_home.py`：判据是纯函数，源码进、事实出；合成红证在同一个文件里）：
  1. `webapp` 里 `global` 语句数 = 0；
  2. `webapp` 模块级没有「会话态形状」的赋值（空容器 `set()` / `{}` / `[]` / `dict()` / `list()`
     与 `None` 占位）——非空的常量表（平台展示名那类）不算；
  3. 三个名字不出现在 `webapp` 的模块级赋值与 `global` 名单里，也不出现在 `tests/` 对 `webapp`
     的跨缝 import 里；
  4. 正向：`AppContext` 的 dataclass 字段含这三个名字（防「把状态删掉」式假绿）；
  5. 合成红证：把收走前的写法（模块级 `X = set()` / `{}` / `None` + `global X`）喂进同一套判据，
     当场认出。
- **真红证**：`.scratch/webapp-state-into-ctx/probe-01-pin-red-proof.py` 把**收走前那个提交**
  （显式钉 `5c9fc8b0`，**不写 HEAD**）的 `webapp.py` 与全部测试源码喂进同一套判据 → 6 条
  违规（4 类）；当前树 → 0 条；**base 自校验**：base 版里若已经找不到那三处模块级状态就大声
  失败（选错 base 不许产假绿）。判据**只有一份聚合函数**（`state_violations`），探针与守卫共用。
- **全绿**：`python -m pytest -n auto -q` 全绿；`node --test "tests/js/*.test.mjs"` 全绿
  （前端只动过一行注释，属回归确认）。

## 范围外

- 把模块级 `app = create_app()` 撤走（uvicorn 入口契约，硬约束）。
- 完整包链路的模块级会话态（另议）。
- C7「73 个私有符号被测试翻墙」——当验收尺用，本条不碰。
- 其余前端改动（含 `fx/task.js` 除那行注释外的任何字节）。
- 墓碑注释 / 顺手重命名 / 顺手改工具根或快照路径。

## 补充说明

- **为什么并行跑用例更安全（本条卖点，口径写清）**：
  - 收走前：这三样是**进程级**的。`pytest -n auto` 的 worker 是独立进程，所以「跨 worker」
    本来就不共享；真正的问题在**同一个 worker 内**——用例之间共享（靠 autouse 夹具**事后**
    清扫压住），同一用例里两个 app 实例也共享（无药可救）。那夹具写在「答案之后」：它保证的
    只是「下一个用例开始时干净」，中间态对本用例与其他实例始终可见；新写的用例文件忘了抄它
    就会中招。
  - 收走后：状态随 ctx 走，注入与断言都在**自己构造的实例**上（`ctx.materials_last_check.update` /
    `ctx.running_task_execs.add`），模块全局再没有可写的东西；两个实例天然互不可见（两条新行为
    判据钉住）；清扫夹具退场——新用例不必抄任何夹具，也不可能被邻居污染。
  - 与 `hwcheck_recipe_path` 先例的关系：那条治的是**共享文件**（并行 worker 读到真库的半截
    写入），本条治的是**共享内存对象**；同一种病（进程级共享 = 隐式耦合）的两个面，机制不同
    （注入路径 vs 注入上下文），故不合并。
- **三处会变假的旧名字引用**（随最后一单改）：`CONTEXT.md` 的任务推进词条、
  `materials_task.ApplyTask` 的类 docstring、`static/js/fx/task.js` 的一行注释。
- `docs/agents/local-environment.md` 按既有惯例补一行本轮会话事实（本轮没起服务器、读数），
  第 0 节的发布落差表不动。
- 判据口径：本条的验收不是「引用行数变少」，而是**每条 app 实例拥有自己的状态 + 模块级不再
  有那种形状 + 既有判据零削弱 + 两个实例互不可见这条行为能被测出来**。
