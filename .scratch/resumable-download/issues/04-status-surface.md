# 04 — 状态面新增三字段：retrying / retry_count / error_kind

**要做什么：** 让界面**知道**「现在是在重试、重试了几次、失败属于哪一类」——
在这之前前端只能从 `error` 文案里猜，猜不到就只能把「慢」「卡」「失败」显示成一个样子。

**被谁阻塞：** 03（任务层有重试状态可投影）。

**状态：** resolved

- [x] `task_status`（`materials_task.py`）与 `full_task_status`（`full_task.py`）**新增**三个字段：
      `retry_count: int`（当前卷累计自动重试次数）、`retrying: bool`（是否正处在退避等待中）、
      `error_kind: str`（`""` / `"network"` / `"verify"`）。
- [x] **既有字段一个不改**（`state` / `parts` / `total_downloaded_bytes` / `total_bytes` / `speed_bps` /
      `current_part_name` / `error` / `message`）——前端零破坏；新增字段在 idle 空态也要在场（值 0 / false / ""）。
- [x] `message` 字段语义定死并接线：**进行中的摘要**（重试中原样透出），**终态清空**（终态原因只走 `error`）。
- [x] 单测：三字段在 idle / downloading / 重试中 / failed(network) / failed(verify) / done 六态下的取值矩阵；
      以及一条**结构守卫**——断言 status 响应**包含**这 8 个既有键（防以后有人顺手改名）。
- [x] 端点侧不改协议：`/api/update/full/status` 与资料库 `status` 直接透出新字段即可，**不加新端点**。

## 验收记录（2026-09-13）

**契约测试集中在一份新文件**：`tests/test_download_status_surface.py`（19 条，两条链路各跑一遍
同一套矩阵）。为什么不散进两个行为测试文件：状态面是**前端唯一的信息来源**（前端不许解析
`error` 文案来分类），六态矩阵要能一眼看全；散在各行为用例里就看不全了。

**六态矩阵**（`full` / `materials` 两条链路参数化跑同一套断言）：

| 态 | `state` | `retry_count` | `retrying` | `error_kind` | `message` | `error` |
|---|---|---|---|---|---|---|
| idle（无任务） | `idle` | 0 | False | `""` | `""` | `""` |
| downloading | `downloading` | 0 | False | `""` | `""` | `""` |
| 退避等待中 | `downloading` | ≥1 | **True** | `network` | 「…第 N 次自动重试…」 | `""`（重试中不算失败） |
| failed(network) | `failed` | ≥1 | False | **`network`** | `""` | 「下载失败（卷 …）」 |
| failed(verify) | `failed` | 0 | False | **`verify`** | `""` | 「…校验失败（SHA256 不匹配）」 |
| cancelled | `cancelled` | 0 | False | `""` | `""` | `""` |
| done | `done` | ≥1（本次重试过） | False | `""` | **`""`** | `""` |

「退避中」那一行用**真线程 + 真 socket**测（`retrying` 只在退避窗口里为真；构造出来的假状态
测不到窗口什么时候开、什么时候关）：轮询到 `retrying` 为真时抓快照，跑完再断言终态已清空。
（测试文件 `tests/test_download_status_surface.py`，19 条 = 两条链路 × 六态 + 字段守卫。）

**本单改掉一处真缺陷（矩阵测试抓出来的）**：`error_kind` 原来一律走
`download_resume.error_kind(exc)`，而**校验失败**是任务层自己判出来的普通 `OSError`
→ 被归成 `network`。后果正是 spec 想避免的那件：前端会把「内容不对，重下也不会有变化」
说成网络问题，并给出「点击重试会从这里接着下」这种误导话术。修法：校验失败抛带
`error_kind = "verify"` 标记的异常（`materials_task._verify_error`），任务层分类时先认标记
（`_classify_error`）。两条链路各一条用例钉住。

**两处分层守卫**（防以后回退）：

- `test_download_resume_module_has_no_status_knowledge`：下载域模块不认识 `retrying` / `retry_count`
  ——`error_kind` 这个名字在同一份代码里有**两层含义**（下载域的分类函数 vs 状态面的字段），
  哪天有人把状态字段的取值逻辑塞回下载域，这两层就开始互相污染；
- `test_snapshot_does_not_carry_retry_state`：重试观测是内存态，**不落快照**
  （重启后从 0 重新计更诚实）。

**端点侧**：不加新端点、不包一层——两条 `status` 端点直接透出（`test_endpoints_expose_new_fields`
对 `/api/update/full/status` 与 `/api/update/materials/status` 各断言一次字段全集）。

**与 03 的关系**：字段与投影在 03 就位（03 的验收标准要求「重试消息进任务摘要」），
本单做的是**把语义钉死 + 矩阵化取证**——03 的探针与用例只覆盖到「用到的那几个瞬间」。

## 双轴评审结论（2026-09-13）

评审对象 = 本单未提交改动（`git diff HEAD`，HEAD = `30f155b8`）。两条轴的问题都**当场修掉**，
因为它们中的大多数是同一件事的不同侧面：**「重试窗口」与「分类词表」的边界没定死**。

**Standards 轴：1 条硬违规（分类源裂成两处）→ 已按评审建议重做**

原实现（本单第一版）让任务层给异常动态挂 `error_kind` 标记、再自建 `_classify_error` 认领，
于是「状态面 `error_kind` 的单源」变成两处，且 `full_task` 反过来 import `materials_task`
的私有名（两个同层任务模块互相依赖）。改法：分类**回下载域**——
`download_resume` 谱系补一支 `DownloadVerifyError`，`error_kind` 加一条映射；
任务层只抛出这个类型，分类仍只有一处；`_classify_error` / `_verify_error` 两个补丁一起删掉。
另修 `describe_network_error` 的处理分支与 `error_kind` 的 docstring（原注释与既有代码不符）。

**Spec 轴：4 处 → 已全部修**（其中两处是本单第一版的**假绿**）：

| # | 问题 | 修法 | 判据 |
|---|---|---|---|
| 1 | **退避中取消**那一格假绿：`cancelled` 行断言的是「run 前就取消」（那两项本来就是 0，怎么断言都过）；真正的路径（先失败一次 → 进退避 → 用户点取消）会留下 `retry_count=1 / error_kind="network"`，前端据此把用户自己点的取消报成网络故障 | `except DownloadCancelledError` 里把重试观测一并归零 | `test_cancel_during_backoff_clears_retry_state`（两条链路，真 socket） |
| 2 | `message` 的「终态清空」只做了一半：退避窗口关闭时只清 `retrying`，摘要会挂满剩下整段下载（`retrying=False` + `message=「正在重试第 2 次」`= 自相矛盾，前端只剩解析文案一条路） | 引入 `before_attempt` 回调（退避结束那一刻）统一关窗：`retrying` 与 `message` 一起清 | `test_message_cleared_when_backoff_window_closes` + `test_retry_window_closes_when_backoff_ends` |
| 3 | 结构守卫写成**集合相等**，将来合法新增字段会无故转红（工单要求的是「包含既有 8 键」） | 改成子集断言（既有键 ⊆、新键 ⊆） | 同一条用例 |
| 4 | **应用阶段失败**也被分类：解压 / 磁盘写入错误 → `error_kind="network"`，前端会说「点重试会接着下」——正是本单想消灭的那种误导 | 应用分支留空（词表没有这一格 → 走通用话术） | `test_apply_phase_failure_has_no_error_kind` |

**同轴另两条已核实成立**：8 个既有字段名逐字未改；取消路径不产出词表外的 `"cancelled"`；
重试观测不落快照；无新端点。词表收口改用类型判定后由其自身保证
（`test_error_kind_vocabulary_is_closed` 覆盖六个异常类型）。

**评审期间发现并修掉的一处自家 bug（窗口宽度）**：第 2 条的修法第一版把「关窗」放在
`on_start` 里——而 `on_start` 与 `before_retry` 在同一轮循环里紧挨着发生，于是窗口被压成
**0 宽**：`retrying` 永远观察不到为真。改成在**退避等待结束之后**回调 `before_attempt` 才关。
这条是「用轮询写窗口断言」引出来的：轮询要跟 0.3 秒的窗口赛跑，第一版就假绿过
（`retrying` 恒假而 `retry_count` 已是 1）——现在两条用例一条在开窗那一刻抓快照、
一条合成断言窗口回调，都不赛跑。

**回归**：全套 4425 passed / 1 skipped；`probe-03-corridor.py` 复跑总判 PASS（三个用例全绿）。


## 备注

- `error_kind` 是给前端**选话术**用的，不是给用户看的字符串——前端不许解析 `error` 文案来分类。
- 本单不动前端：前端消费在 05。
