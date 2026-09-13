# 09 — 结构重排：两条链路的重复长出来两层，收成一个「重试观测」值对象

**要做什么：** 让「重试观测」这件事在代码里有**一处**定义——两条任务链路
（完整包 / 资料库）不再各自维护同一套字段与同一套回调，改一处两处都变；
并且**外部可见的字段名一个不改**（状态面契约与既有测试的注入点都靠它）。

**被谁阻塞：** 无——可立即开始（工单 03 的评审留的账，04/05 又加了第二层，08 顺手清了第三层）。

**状态：** resolved

- [x] 把「重试观测」的六个散字段（`retry_count` / `last_retry_at` / `last_error_kind` /
      `_retrying` / `_resume_percent` / `_message`）收成一个值对象，语义集中一处：
      清空、取消时归零、退避开窗 / 关窗、每卷复位——这些**规则**现在两边各写一遍，
      已经漂过一次（工单 04 评审发现「退避中取消」那一格两边都漏了）。
- [x] 四个近乎逐字重复的回调（`_on_progress` / `_on_attempt_start` /
      `_on_retry_window_closed` / `_on_retry`）收成共享实现。
- [x] **字段名与语义零改动**：`retry_count` / `retrying` / `error_kind` / `resume_percent` /
      `message` 的状态面契约、以及既有测试里 `task.retry_count = 5` 这类直接注入，
      行为与可读性都不变。
- [x] **零行为变化**：既有判据（工单 03/04/05/08 与探针）全程保持绿，不许调整任何断言
      来迁就重排。
- [x] 工单 03 评审点名的另一条（`_download_one` / `_resolve_download` 约 40 行重复）
      **本单不做**，见「备注」——它与本单不同性质。

## 为什么值得做（不是洁癖）

重复的不是「几行字」，是**规则**。现在这套规则在两条链路上各写一遍，已经付出过代价：

| 规则 | 现在住在哪 | 漂过的证据 |
|---|---|---|
| 退避开窗：`retrying=True` + 摘要只说原因 | `full_task._on_retry` / `materials_task._on_retry` | 工单 04 修「0 宽窗口」时两边都要改 |
| 退避关窗：`retrying=False` **且**摘要清空 | 两处 `_on_retry_window_closed` | 工单 04 评审：只清一个会留下自相矛盾的状态组合 |
| 取消时把重试观测归零 | 两处 `except DownloadCancelledError` | 工单 04 评审：**两边都漏了**，各补一次 |
| 换卷复位 | 两处 `run()` 的卷循环开头 | 工单 04 的 `test_retry_state_resets_per_part` 是两边各一条 |

「两边各改一次、漏一边就出 bug」正是这个形状最贵的地方——本单把它压成一处。

## 备注

- **同层依赖方向不许破**：共享件放**新模块**，`download_resume`（下载域）保持不知道
  状态面字段名——`tests/test_download_status_surface.py::test_download_resume_module_has_no_status_knowledge`
  就是这个方向的守卫（工单 04 立的）。共享件依赖 `download_resume` 的策略函数，反向不许。
- **`_download_one` / `_resolve_download` 那 40 行重复本单不做**：它与本单性质不同——
  那是两个**业务流程**长得像（一个扁平分卷、一个按批次分组），强行合并要么参数化出一堆
  回调、要么把批次概念塞进完整包；而本单这四处是**同一件观测**的两份抄写。把不同性质的
  重复混在一单里，评审就没法判断「合并是否值得」。要动那 40 行，另立单。
- 判据沿用本仓库纪律：重排**不产生新判据**——既有判据全绿就是验收线；
  若为了重排而改断言，等于把判据当垫脚石。

  > **这句写错了，评审指出并已更正**：本单**确实**新增了一条判据
  > （`test_retry_observation_has_a_single_home`，钉「重复有没有回来」）。
  > 准确的说法是两件事分开：**既有判据一个断言都不改**（这条做到了，见验收记录），
  > 而**新增一条结构守卫**是必要的——纯重排若不留守卫，下次有人把重复抄回来时
  > 没有任何东西会红，「以后不会再漂」就只是愿望。

## 验收记录（2026-09-13）

### 一、结果：225 行重复从两条链路里消失，判据一行未改

| 文件 | 变化 |
|---|---|
| `src/contest_generator/task_retry.py` | **新增 316 行**（字段的家 + 规则 + 回调工厂 + 注释） |
| `src/contest_generator/full_task.py` | **−120 行**（四个回调 + 两处复位块 + 投影改读属性） |
| `src/contest_generator/materials_task.py` | **−105 行**（同上） |
| `tests/test_download_status_surface.py` | +142 行（**全部是新增**：结构守卫一条 + 它的三个 helper） |

净增 4 行，**但重复的 225 行没了**，且注释放进了一处（说明「为什么」的文字在两条链路上
本来也是同一份）。`git diff --stat` 里 `tests/` 那两个数是 **108 insertions / 0 deletions**
——既有断言一个字没动，这是本单唯一的硬验收线。

### 二、零行为变化：两轴独立核对，逐条对过

评审把每个被替换的写入点逐个对照，结论「**all paths are exact**」：

| 共享方法 | 等价于旧代码 |
|---|---|
| `reset()` | 六条赋值（含 `resume_percent = -1`），值完全相同 |
| `reset_for_cancelled()` | 旧取消路径只清四条（**本来就不清 `last_retry_at` / `resume_percent`**，见第四节） |
| `close_window()` | 旧 `before_attempt` 的两条（**顺序也是 `retrying` 再 `message`**） |
| `note_retry()` | 字段写入顺序与 `time.time()` 取值都不变 |
| `part_progress_callbacks()` | 返回 `(on_progress, on_start)`，与旧的两个方法同签名；`**retry_callbacks(part)` 不产生重复 kwargs |
| 三处状态投影 | 读到的值完全一致 |

另有两处**看似改动其实无副作用**，也已核实：`materials_task` 里把
`was_applying = …` 提到清空之前（两个清空都不碰 `_state`）；
`_message` / `_retrying` / `_resume_percent` / 回调可调用对象在旧代码里也是
**在 `as_task_downloader(...)` 之前**求值的，新代码同样——没有多出来的抛错时机。

回归：**4434 passed / 1 skipped**；`probe-01-resume.py` / `probe-03-corridor.py` /
`probe-08-416.py` 复跑总判全 PASS。

### 三、新守卫真的会红（防「守卫只是装饰」）

反向验证：往 `full_task.py` 尾巴塞一个「四条赋值 + 一个 `_on_retry` def」，
守卫立刻转红并指名道姓：

```
AssertionError: full_task.py 又出现成块的重试观测赋值：
  [['retry_count', 'last_retry_at', 'last_error_kind']]（复位应走 TaskRetryState.reset…）
```

**第一版守卫是弱的，评审指出后已加固**（这条值得记下来）：

| 原判据 | 问题 | 现在 |
|---|---|---|
| 「这六个字段只许在 `task_retry` 里被赋值」 | **假命题**：失败路径要写 `last_error_kind`、下载完成要清 `message`，都在任务层 | 改成认**形状**：连续 ≥3 条赋值都写这六个字段 = 复位块（单条分散写入不算） |
| 第 3 条 `task_retry 里 ≥6 个字段被赋值` | **几乎是空断言**：mixin 自己的属性 setter 就能满足它，值对象就算废掉也绿 | 改成**按方法逐个查**：`reset` 必须写全六个、`reset_for_cancelled` 必须写那四个、`close_window` 必须同时写 `retrying` 与 `message` |
| 没查两条链路是否还继承 mixin | 有人删掉继承，前两条照样绿 | 新增：`issubclass(cls, TaskRetryMixin)` + `_retry_state` 已实现（不是桩） |

### 四、一处「不对称」如实记账（不是本单改的）

`reset_for_cancelled()` 清四个字段、`reset()` 清六个——**看着像漏，其实是对既有行为的
如实搬运**：工单 04 定的取消路径本来就只清那四个。不对称是安全的，理由已写进 docstring
并逐条核实：

- `resume_percent` 只在「正在重试」那一支被前端读到（`fx/full-update.js:121`、
  `fx/materials-update.js:113` 都是 `s.retrying ? … : …`），取消态 `retrying` 为假 → 用户不可见；
- `last_retry_at` **压根不进状态投影**（它是排障观测值，「上次重试发生在几点」取消后仍是真的）。

要让取消态把这两个也清干净，那是**行为变更**，得配判据、另行开单——不塞进纯重排。

### 五、兼容别名的代价（如实记，不当成免费）

为了让既有判据一个字不改，`TaskRetryMixin` 保留了四个私有名的兼容别名
（`_message` / `_retrying` / `_resume_percent` + 三个私有回调转发）。
**代价**：这几个名字现在**有两个住处**（值对象 + mixin 属性），
「六个字段名一个不改」实际是「一个公开的家 + 三个遗留别名」。

接受它的理由：判据的价值高于内部形状的纯度，而工单 09 不准改断言。
**新代码不许用这四个名字**（注释里已写死）。要清理是独立一步——连测试一起改，
不该混在纯重排里做。评审对这个取舍的判定是「justified, not scope creep」，
但也如实指出它把「单一家」的目标打了个折。

### 六、本单没做的事（别读大）

- **没动 `_download_one` / `_resolve_download` 那 40 行**（工单 03 评审的另一条账）：
  那是两个**业务流程**长得像（扁平分卷 vs 按批次分组），与本单「同一件观测被抄两遍」
  性质不同，混在一单里评审就没法判断「合并是否值得」。要动它另立单。
- **没改任何状态面字段名、默认值或词表**（工单 04 的契约面）。
- **没改 `full_task` → `materials_task` 的同层 import**（`TaskState` / `_file_sha256`）：
  评审确认这是**本单之前就有**的，与本次重排无关；顺手拆它会扩大爆炸半径。
- **没清兼容别名**（第五节）——那是「一个名字有两个住处」，与本单「同一件观测被抄两遍」
  不同轴，清理仍是独立一步。

> **归位（本单结案后补记）**：第六节那笔账已从「备注」搬到工单 **10**
> （`.scratch/resumable-download/issues/10-download-attempt-primitive.md`，`ready-for-agent`）——
> 里面写清了「两个业务流程长得像」与「同一件观测被抄两遍」为什么必须分开判，
> 以及 `_resolve_download` 那 18 行为什么**不**跟它一起收。
