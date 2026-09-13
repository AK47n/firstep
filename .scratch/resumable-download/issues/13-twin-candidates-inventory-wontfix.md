# 13 — 同形重复盘点：状态视图 / `run()` / 快照封套 / `__init__` / 单行取值器——量清了，**不动**（wontfix）

**要做什么：** 把工单 11 备注里留下的四类「同形重复」候选逐个量清（改动前的形状从
`git show` 取，结论可复现），然后**做出结论**：哪些值得动、哪些不值得。本单的结论是
**除 `_PartState` 里那半没人用的代码（另立工单 12）之外，其余一处都不动**——
量出来的账不支持「漏一边就出 bug」，而工单 10 第三节的判据说得很清楚：
**不许为了对称好看动热路径**。

**被谁阻塞：** 无——工单 11 已 resolved（`ea0ae09d`）；本单与工单 12 并行，
两者不共享改动面（12 动 `_PartState` 的没用的那半 + 契约判据强度，本单**零代码改动**）。

**状态：** wontfix

- [x] **先量再动**：`measure-12-twin-candidates.py`（基线 `git show 5461f39d`）把 12 对同名函数
      全量对过：代码行 / 逐行相同 / AST 同形 / 语句同形 / 数据形状逐字段 / 两文件同提交次数。
- [x] **判据强度实测**：`probe-12-guard-strength.py` 错版注入十格（逐文件跑、卡住不作判据，
      每格先自证注入生效），答「既有用例对这两份各自覆盖到什么程度、错了会不会红」。
- [x] **结论写回本单**：四类候选逐条给「为什么不值得动」，附可复跑的原始输出
      （`verify-12-duplication.txt` / `verify-12-guard-strength.txt`）。
- [x] **只留下一条真实可动的**（工单 12）：`from_dict` 零调用点 + 两侧契约断言不等强——
      那两件事**不是因为重复**才做，而是因为「有死代码」与「判据不等强」被量出来了。

## 一、量出来的账

| 候选 | 代码行 full/mats | 逐行相同 | AST 同形 | 真正不同的行 | 判据强度（错版注入） |
|---|---|---|---|---|---|
| ① 状态视图 `full_task_status` / `task_status` | 45 / 45 | **43** | 否 | **2**（签名 + 卷怎么枚举） | **两侧各自都红** |
| ② `run()` | 45 / 43 | 38 | 否 | 14（循环形状 + `on_complete` 契约 + 异常分支写法） | **红**（`keep_current_name`：1 failed；`no_error_kind`：status 面 2 failed） |
| ② `_write_snapshot` | 14 / 14 | 13 | 否 | **1**（封套键 `parts` vs `batches`） | **推断为红**（未单独设错版格）：封套键被改 / 缺席会让 `test_snapshot_written_and_recoverable`（全）与 `test_write_task_snapshot_roundtrip`（资料库）在读回时取不到 `parts` / `batches`——但那是**读码推断**，不是本单量到的；量到的相邻事实是工单 12 的 `drop_field` 格：`to_dict` 漏字段**既有判据全绿**（80 passed），说明这一族判据只在「读回」那一步才生效 |
| ② `__init__` | 32 / 41 | 23 | 否 | 26（单向表 vs 批次树、`Path()` 包装、缺省下载器写法） | **红**（错版把卷名吞成空串：`test_full_task.py` 15 failed） |
| ④ `state` / `error` / `cancel` | 2 / 2 | 2 | **是** | 0 | **红**（把 `state` 钉成常量：`test_full_task.py` 22 failed；把 `error` 钉成空串：3 failed + status 面 3 failed） |
| ④ `_retry_state` | 2 / 2 | 2 | **是** | 0 | 红（mixin 与 24 处调用；与 `state`/`error` 同族，不另设错版） |
| （对照：**判据无效**的两格）速度估算公式 | 两侧同一段 | — | — | — | **两侧都绿**（见本节末） |
| （对照）已收的 `_resolve_download` / `_restore_snapshot` | 2 / 4 行壳 | — | — | — | — |

**「判据无效」那两格的原始数（本单唯一一处既有判据真空白，且两侧对称）**：
把状态视图里的速度估算改成恒 `0`（`speed_bps: 0`）→ `test_full_task.py` **33 passed**、
`test_materials_task.py` **20 passed**（全绿）。原因是既有断言只到
「`isinstance(int)` / `>= 0`」这一层（`tests/test_full_task.py:699` / `710`），
而前端是防御式读法（`s.speed_bps || 0`），于是**这个字段坏了没有任何判据会红**。
它与「收重复」无关（两侧**对称**地缺判据，不是「漏了一边」），故不构成本单或工单 12 的理由，
只作为事实记在这里（要补是「加强判据」，另一件事）。

## 二、逐条：为什么不动

### ① 状态视图（90 行 / 45 行相同）——**最像**的一处，但判据是对称的，且没付过代价

- **真正不同的只有 2 行**：函数签名（类型注解）与「卷怎么枚举」
  （`for p in task.parts` vs `for b in task.batches for p in b.parts`）；其余 43 行逐字相同。
  形状上属「长得像」而非「抄」：**枚举方式不同这件事是真实的**，它也正是工单 10/11 划缝的位置。
- **判据强度实测（错版注入，逐文件）**：
  - 去掉契约字段（`retry_count` / `retrying` / `error_kind` / `resume_percent`）→
    `test_full_task.py` **5 failed**、`test_materials_task.py` **1 failed**、
    `test_download_status_surface.py` **13 / 10 failed**；
  - 把载荷键 `parts` 改错名 → 两侧同样转红（full 4+3 failed / materials 1+3 failed）。
  → **没有「一处有人看、一处没人看」的不对称**（对比工单 11：materials 侧哈希校验当时是真空，
  探针实测 47 passed——那才是收它的理由）。
  *口径*：`test_download_status_surface.py` 在「去掉契约字段」那两格里有**一支**用例
  （`test_message_cleared_when_backoff_window_closes`）会**稳定打转**
  （`-o faulthandler_timeout=25` 转储把它钉在第 355 行；>600s 也不返回）——
  那是本机已知的间歇性卡死被注入改了时序后稳定复现，**不作判据**，
  该格用 `-k 'not …'` 排除它、其余 27 支照跑（原始输出见证据文件）。
- **历史给的是双份维护成本，不是 bug**：`22d0f643`（工单 03）、`54fff91b`（工单 05）、
  `918f25b4`（工单 09）三次**两边各改一次**，其中 `54fff91b` 的 diff 显示
  「`resume_percent` 字段 + 注释 + 那一整段」在两文件里**逐段对应**。
  但**没有一次是「改了一边、忘了另一边」**——所以按工单 10 第三节的判据，
  动它是「纯洁癖」而非还账。
- **要收的话缝在哪（写下来，供将来真要做时用）**：共享核心 = 「PartLike 表 → 12 键载荷」
  （含速度窗口记账），入参只多一个「卷从哪来」；两侧各自剩一句转发（与
  `_resolve_download` / `_restore_snapshot` 的壳同形）。净省约 45 行，但**结果是零行为变化**，
  要动的是**每一次 status 轮询都走的那条路**——按工单 10 第三节，收益不抵风险。

### ② `run()` / `_write_snapshot` / `__init__`——承载的确实不是同一件事

- `run()` 的 14 行不同里，**5 行是实打实的契约差异**：`on_complete(...)` 一侧收分卷清单
  （应用器按它找文件）、一侧不收；循环是一层 `for part in self.parts` vs 两层
  `for batch in ... for part in ...`；异常分支的写法是条件表达式 vs `if/else`
  （语义等价，量具按逐行比会记成不同）。顺序敏感（`_state` / `_write_snapshot` 的时机）
  而两侧各自有专门用例在看。
- `_write_snapshot` 只差**封套键那 1 行**（`parts` vs `batches`）——它是快照文件格式的
  一部分（工单 03/11 的断点恢复直接读它），不是重复写错。
- `__init__` 的 26 行不同正是「单向表 vs 批次树」的全部内容（含 `_part_name` 的卷名口径、
  `Path()` 包装、缺省下载器的两种写法）——这一处**长得像**是巧合，两边的输入契约不同。
- **要收就只能参数化**（把循环体做成回调、把封套键做成参数），那正是工单 10 明禁的
  「引入一组回调参数」——缝会划在错的维度上。

### ③ 单行取值器（`state` / `error` / `cancel` / `_retry_state`）——收益为负（数据确认）

- 每处**实现体 1 行**（`return self._x`），两处共 2 行；收它的唯一方式是**再加一层**
  （共同基类 / 再一个 mixin）→ 新增间接层比省下的 2 行更贵。
- `_retry_state()` 是被 `TaskRetryMixin` 当**抽象钩子**用的（24 处调用），
  两侧各实现一次是**契约要求**（每侧自己建 `TaskRetryState`），不是重复。
- 判据强度（**实测**，不是推断）：把 `state` 钉成常量 `IDLE` →
  `test_full_task.py` **22 failed** + status 面 **9 failed**；把 `error` 钉成空串 →
  `test_full_task.py` **3 failed** + status 面 **3 failed**。它们是**公开状态面**
  （前端与 `status` 投影都读），形状一致是**要求**而非重复。
- 结论：**wontfix**（数据确认：实现体各 1 行、两处共 2 行，收益为负）。

## 三、探针自己栽的**四次**（记下来，别重演）

1. **第一版错版把「速度窗口记账」一起丢了**（`task._last_ts` / `_last_bytes` 的就地更新），
   于是 `tests/test_download_status_surface.py::test_message_cleared_when_backoff_window_closes`
   在注入下**打转不返回**（它的 spy 每次进度回调都调 status，窗口不动 → 退避空转），
   探针只能报「失效」。**处置**：错版只丢**要测的那部分**，其余逐字保留（分离变量）。
2. **错版正文里 `_time` 没进 `exec` 的名字空间** → 错版一调用就 `NameError`，
   被下载重试路径吞掉 → 多支用例**空转**（表现与第 1 条一样）。**处置**：
   `ns = {"_time": _time, ...}`，并在注释里写明「注入生效」的自证必须包含
   「错版真的能跑完一次」这一层（工单 11 的第一版探针就是栽在类似处：
   报「绿」其实是注入没生效）。
3. **第一版 `__init__` 错版把卷大小吞成 0** → 真下载在重试退避里打转（**自己造的卡住**）。
   **处置**：换成「卷名不解析」这种**确定性失败**的错版（`tests/test_full_task.py` 15 failed）。
4. **新增三格的 `build_plugin` 忘了给 `init` / `getter` 两种 kind 填 `__INIT_SRC__` 槽**
   → 插件自己 `NameError` → 探针如实报「探针失效」（**没有**折算成绿）。**处置**：
   补上分支后逐格复跑，三格都给出判据。

四次都不是产品行为，都是探针失真——**「不许把探针的假形状当成产品行为」**（工单 11 立的纪律）。

## 四、证据（**与工单 12 共用同一批工具与证据文件**：它们分别回答「哪一处值得动」与「其余为什么不值得动」）

| 文件 | 内容 |
|---|---|
| `.scratch/resumable-download/measure-12-twin-candidates.py` | 量具（基线 `git show 5461f39d`，可复跑） |
| `.scratch/resumable-download/verify-12-duplication.txt` | 量出来的账（改动前 / 现状两张表 + `_PartState` 逐字段 + git 历史） |
| `.scratch/resumable-download/probe-12-guard-strength.py` | 错版注入探针（十三格、逐文件跑、每格自证注入生效） |
| `.scratch/resumable-download/verify-12-guard-strength.txt` | 判据强度原始输出（含「卡住不作判据」的记录与复跑诊断） |
| `.scratch/resumable-download/rerun-12-case.py` | 单格复跑器（诊断用：某格失效时看原始输出） |
| `.scratch/resumable-download/run-12-evidence.py` | 证据落盘器（UTF-8，由脚本落盘，不走 shell 重定向） |
| `.scratch/resumable-download/issues/12-part-state-shape-and-contract-parity.md` | 本单量出来的**唯一动代码处**（`from_dict` 死代码 + 契约判据不等强） |

## 备注

- **本单零代码改动**：它是**判定单**（量清 → 关掉），代码改动全在工单 12
  （`from_dict` 与契约判据强度）。这样两者各自可评审：一个判「值不值得动」，
  一个判「删得对不对」。
- **别把「wontfix」读成「没做」**：四条结论各自带量具输出与探针原始输出；
  将来谁想推翻，先跑 `measure-12-twin-candidates.py` 与 `probe-12-guard-strength.py`。
- **工单 11 的备注里那四条「为什么当时不动」的理由，本单逐条自己量过**：
  第 ① 条（状态视图）理由成立但依据换成了实测；第 ② 条（`run()` / `_write_snapshot`）
  成立；第 ③ 条（`_PartState`）**部分推翻**（乘一半是死代码 → 工单 12）；
  第 ④ 条（单行取值器）成立且用数据确认了「收益为负」。
