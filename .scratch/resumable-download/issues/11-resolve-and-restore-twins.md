# 11 — `_resolve_download` 与 `_restore_snapshot`：一对真抄 + 一对长得像，收哪一处、凭哪条判据

**要做什么：** 把工单 10 明确留在第七节的两处同形重复**先量清楚再决定**：
`_resolve_download`（两处**逐字相同**的 7 行代码）与 `_restore_snapshot`（两处 21/26 行、
去噪后相同 16 行，但卷的组织方式不同：扁平 parts vs 两层 batches）。
量出来的账支持收**前者**，且**只收前者**——后者只把那 16 行的**逐卷恢复原语**收一处，
两层的遍历留在各链路（缝不能划在「形状不同」的那一段上）。

**被谁阻塞：** 无——工单 10 已 resolved（`3fc218b4`），其第七节明文把这两处留作另立单。

**状态：** resolved

- [x] **先量再动**：三把量具 + 三支探针，全部落盘可复跑（见「验收记录」第一、二节）。
      量出来的账：`_resolve_download` 两处**代码 7 行逐字相同、AST 去名后同形**；
      `_restore_snapshot` 代码 21/26 行、相同 16 行、**AST 去名后不同形**（多一层批次）。
      git 历史：`_resolve_download` **一次创建、两处各抄一遍**（`22d0f643` 同一提交）；
      `_restore_snapshot` 两处**分别**引入（`189d105c` / `786dc450`），此后**本体一次都没改过**。
- [x] 收 `_resolve_download`：两处的壳留一行，解析顺序（实例属性 → 类属性 → 缺省）
      收进 `task_download.resolve_task_download`。**注入缝契约显式钉住**：
      `monkeypatch.setattr(<Task>, "_download", fake)` 两处都必须仍然生效（新增判据）。
- [x] 收 `_restore_snapshot` 的**逐卷恢复**那 16 行（快照封套 + ok 判 + 文件在否 +
      内容哈希 == 清单 sha → 三个字段一起恢复），进 `task_download.restore_snapshot_parts`；
      **两层的遍历留在各链路**（`iter_parts` 由调用点给）。
- [x] **零行为变化**：既有判据全程绿，`git diff --stat` 里 `tests/` 既有文件 **0 deletions**；
      错版注入探针证明改动的两处**都在判据的射程内**（第四节）。
- [x] 新增**一条结构守卫**（两处同形不许再回来）：任务模块里 `_resolve_download` /
      `_restore_snapshot` 必须是**薄壳**（只许「调用共享件」这一句），并做**反向注入验证它会红**。
- [x] 顺手补上**材料库那一侧缺掉的判据**：`_restore_snapshot` 的哈希校验在 materials 侧
      **原先没有任何判据**（探针实测：错版全绿），补一条与 full 侧对偶的用例。
- [x] 双轴评审；判定记进「验收记录」。

## 先说清代价（为什么这一单成立、边界在哪）

### 一、量出来的账：一处是「真抄」，一处只是「长得像」

`.scratch/resumable-download/measure-11-duplication.py`（逐行 + AST 两把尺）与
`measure-11-surface.py`（把两文件**所有同名函数**全量对一遍）：

| 函数 | 代码行（去 docstring/注释） | 完全相同行 | AST 去名后同形 | 判读 |
|---|---|---|---|---|
| `_resolve_download` | 7 / 7 | **7** | **是** | **真抄**（一个字符不差） |
| `_restore_snapshot` | 21 / 26 | 16 | 否 | 前 16 行真抄 + 后 5/9 行是两种组织方式 |

全量对下来（14 个同名函数）：**AST 同形的只有 7 个**，其中 5 个是
`state` / `error` / `cancel`（单行取值器，与 `_retry_state` 同类）与 `to_dict` / `from_dict`
（`_PartState` 数据形状）——**那两个数据形状是全仓另一条账，本单不碰**（第五节的边界）。

### 二、历史取证：一处付过代价、一处没有

| 证据 | 性质 | 说明 |
|---|---|---|
| `22d0f643`（工单 03） | **硬证据**：同一提交给两文件各加一遍**逐字相同的 `_resolve_download`** | 引入即双份；对照 `git show` 的两段 hunk，除 docstring 外一字不差 |
| `git log -S'instance is None or instance is resumable_download'` | 该解析逻辑**只被改过一次**（就是创建那次） | 双份至今没同步过一次——但这**不构成先例**：`_restore_snapshot` 的双份至今也没改过，却正是工单 03 立的「同步」纪律要防的形态 |
| `189d105c` / `786dc450` | `_restore_snapshot` 两处**分别**引入（完整包 / 资料库各一次） | 后来者照抄前者；`git log -S"saved_parts"` 显示此后**本体零改动** |

**这里要老实说清楚**：按工单 10 第四节立的判据（「若 git 历史显示这套序列从未两边各改一次，
本单就退化成纯洁癖」），`_resolve_download` **没有**「漏一边就出 bug」的硬先例。
真正支持收它的是另外两条，都属于**判据强度**而不是**历史频率**：

1. **判据不对称（实测）**：错版注入探针（`probe-11-guard-strength.py`）把
   `_restore_snapshot` 的哈希校验去掉后——full 侧 **1 failed**（
   `test_resume_rejects_tampered_local_file`）、materials 侧 **47 passed**。
   **同一段逻辑，一处有人看、一处没人看**。这正是「双份 + 判据只覆盖一份」的代价，
   而且它今天就在仓库里。
2. **契约面**：`_resolve_download` 是**注入缝的解析器**（工单 10 第七节点名要回答的那个判据问题），
   两份各写一遍 = 同一个契约有两个实现、一个判据（`tests/test_full_task.py:199` /
   `tests/test_materials_task.py:252` 各查自己那一侧）。

### 三、缝划在哪（这是本单唯一有技术风险的决定）

- `_resolve_download`：解析顺序收**共享件**，**方法壳留在各自类上**——
  因为 `download_and_verify(resolve=self._resolve_download)` 与既有判据
  `task._resolve_download()` 都按**方法**取用；收成「基类方法」会动到类层次（工单 10 第七节
  担心的正是这个）。壳留一行 = 调用点与判据面零改动，与既有的 `_retry_state` 壳同形。
- `_restore_snapshot`：只收**逐卷恢复**（对卷的字段做三件事：哈希不认就跳过 / 认了就把
  `ok` / `dest` / `downloaded_bytes` 一起恢复）；`iter_parts` 由调用点给
  （`lambda data: ((p, saved.get(p.name)) for p in self.parts)` vs
  `saved_by_batch → 两层`）。**不引入一组回调参数**——只有一个「怎么遍历」的入参，
  形状差异留在调用点可见。

## 验收记录（2026-09-13）

### 一、先量再动（量具落盘、可复跑）

| 量具 | 命令 | 结论 |
|---|---|---|
| `measure-11-duplication.py` | `python .scratch/resumable-download/measure-11-duplication.py` | `_resolve_download` 7/7 逐字相同、AST 同形；`_restore_snapshot` 21/26、相同 16、AST 不同形 |
| `measure-11-surface.py` | `python .scratch/resumable-download/measure-11-surface.py` | 两文件 14 个同名函数、145 行相同；**AST 同形 7 个**（本单只动其中 1 个 + 1 段） |
| `probe-11-resolve-seam.py` | `python .scratch/resumable-download/probe-11-resolve-seam.py` | 注入缝四格 + 卷级恢复五格，总判 PASS |

`_restore_snapshot` 的五格（两条链路各一遍，落盘在探针输出里）：

| 破坏方式 | 期望 | 说明 |
|---|---|---|
| 完好 | 跳过（不发请求） | 卷级断点的**收益**本身 |
| 同尺寸改坏内容 | 快照被否（`ok=False`）但**不发请求**，终态 `failed` + 校验失败 | 见下面那条「探针自己栽过的坑」 |
| 截断 / 变大 / 删掉 | 不认 → 重下 | 尺寸不同 → 交给重下 |

**探针自己栽过一次（值得记）**：第一版 `_restore_snapshot` 探针写的是「改坏 → 重下」，
跑出来两处都 FAIL。**但它错在期望，不在产品**——「大小对得上、内容不对」那条路会先被
`download_and_verify` 的「长度到点 → 不发请求直接校验」接住（工单 03 立的规则），
终态是 `failed`（如实报校验失败），**不是静默成功、也不重下**。
同时第一版假下载器只在第一次写文件，导致「重建任务后请求没发」被误读成「恢复逻辑没校验哈希」。
已把期望改写成真口径，并把「不许把探针的假形状当成产品行为」写进探针注释。

### 二、探针自己也要自证（第一版探针是失真过的）

`probe-11-guard-strength.py` **第一版四格全绿**，差点被当成「既有判据都不灵」的证据。
真相是探针自己坏了：错版代码塞在 `'''...'''` 里，里面的 `\"\"\"` 落成字面反斜杠 →
`sitecustomize` 语法错 → **注入根本没生效**。修法两条，已写进探针：
① 错版代码只用一个引号层级；② 每格**先自证注入生效**（断言目标类的方法已来自 `<naive-*>`），
注入失败直接判「探针失效」，**不给出绿的结论**。

### 三、判据强度（错版注入，落盘 `verify-11-guard-strength.txt`）

| 错版 | 结果 | 首个红 |
|---|---|---|
| `_restore_snapshot` 去掉哈希校验（full） | **红** | `test_full_task.py::test_resume_rejects_tampered_local_file` |
| `_restore_snapshot` 去掉哈希校验（materials） | **绿（判据无效）** | —— 这就是本单不立结构守卫也要补的那条账 |
| `_resolve_download` 只认实例属性（full+materials） | **红** | `test_full_task.py::test_apply_starts_and_status_reports_progress` |
| `_resolve_download` 永远返回缺省实现 | 逐文件隔离后 full 侧 19+2 failed；两个文件卡在真下载重试退避里 | 见 `verify-11-guard-strength.txt` 末尾的隔离记录 |

### 四、做了什么（改动清单）

| 文件 | 变化 |
|---|---|
| `src/contest_generator/task_download.py` | 新增 `resolve_task_download(task)` 与 `restore_snapshot_parts(snapshot_path, iter_parts)`；docstring 补「本模块还持哪几件任务层共享事」 |
| `src/contest_generator/full_task.py` | `_resolve_download` 18 → **3 行**（薄壳）；`_restore_snapshot` 21 → **4 行**（薄壳）；删掉随之内联的 `download_resume.file_sha256` 调用点 |
| `src/contest_generator/materials_task.py` | 同上；多一个 `_saved_parts_of_batch` 薄壳（两层的遍历留在本文件） |
| `tests/test_download_sequence_home.py` | +2 用例：薄壳守卫 + 反向注入验证（抄回胖身必须转红） |
| `tests/test_materials_task.py` | +1 用例：补 materials 侧缺掉的「快照 ok 但文件被改坏 → 不认」判据（与 full 侧对偶） |
| `tests/test_task_download.py` | +N 用例：两个新共享件自己的行为契约 |
| `.scratch/resumable-download/measure-11-*.py`、`probe-11-*.py`、`verify-11-*.txt` | 量具 / 探针 / 证据 |

### 五、双轴评审结论

（本节在实现与评审之后填。）

## 备注

- **本单的边界**（别读大）：
  - **不动 `_PartState` 数据形状**（两文件各一份 dataclass + `to_dict` / `from_dict`，
    字段逐个相同）。它是「条目库原语」那条账（`entry_store` 先例：参数化劣于清晰重复），
    两个形状今天由 `task_download.PartLike` 协议兜着，动它要连带快照兼容与 `dest` 语义，
    **不在本单**。
  - **不动 `run()` 与 `_write_snapshot`**（39 / 14 行相同）：它们承载的是两条链路**真实不同**的
    状态机与快照封套（`parts` vs `batches`），且 `run()` 的异常分支两侧有实质差异。
  - **不动 `full_task_status` / `task_status`**（状态视图，两处各约 26 行、形状同构）：
    投影字段一样但取数源不同（扁平 vs 展开），属「长得像」——要收是另一单。
  - **不动 `_retry_state` / `state` / `error` / `cancel`**：单行取值器 + 共享 mixin 契约，
    收它们的收益不抵「多一层间接」。
- **依赖方向不许破**：两个新共享件进 `task_download`（任务层共享件的家），
  它已经 import `download_resume` 与 `task_retry`；**反向不许**
  （`test_download_status_surface.py::test_download_resume_module_has_no_status_knowledge` 钉着）。
- **既有的 `_resolve_download` 与 `_retry_state` 同形**：后者早就是「类上一行壳 + 共享件持有规则」，
  本单只是把前者也收到这个形态上——**不是新模式，是回到既有模式**。
- 与工单 09 兼容别名的清理仍是**两件事**（那条是「名字有两个住处」）。
