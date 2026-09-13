# 11 — `_resolve_download` 与 `_restore_snapshot`：一对真抄 + 一对长得像，收哪一处、凭哪条判据

**要做什么：** 把工单 10 明确留在第七节的两处同形重复**先量清楚再决定**：
`_resolve_download`（两处**逐字相同**的 7 行代码）与 `_restore_snapshot`（两处 21/26 行、
去噪后相同 16 行，但卷的组织方式不同：扁平 parts vs 两层 batches）。
量出来的账支持收**前者**，且**只收前者**——后者只把那 16 行的**逐卷恢复原语**收一处，
两层的遍历留在各链路（缝不能划在「形状不同」的那一段上）。

**被谁阻塞：** 无——工单 10 已 resolved（`3fc218b4`），其第七节明文把这两处留作另立单。

**状态：** resolved

- [x] **先量再动**：两把量具 + 两支探针 + 一套逐文件跑法，全部落盘可复跑（见「验收记录」第一、二节）。
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
- [x] **零行为变化**：既有判据全程绿，`git diff --stat` 里 `tests/` 既有文件 **0 deletions**
      （逐条核对见第五节第 13 行；**唯一一处真实行为差异**是「存档项不是字典」时
      由异常兜底改成形状判定，结果相同、已补判据——第五节第 10 行）。
- [x] 新增**一条结构守卫**（两处同形不许再回来）：任务模块里 `_resolve_download` /
      `_restore_snapshot` 必须是**薄壳**（只许「调用共享件」这一句），并做**反向注入验证它会红**。
- [x] 顺手补上**材料库那一侧缺掉的判据**：`_restore_snapshot` 的哈希校验在 materials 侧
      **原先没有任何判据**（探针实测：错版全绿），补一条与 full 侧对偶的用例。
- [x] 双轴评审；判定记进「验收记录」（第五节，含**评审提出的 14 条**与逐条处置）。

## 先说清代价（为什么这一单成立、边界在哪）

### 一、量出来的账：一处是「真抄」，一处只是「长得像」

`.scratch/resumable-download/measure-11-duplication.py`（逐行 + AST 两把尺）与
`measure-11-surface.py`（把两文件**所有同名函数**全量对一遍，两个时刻都量：`3fc218b4` 与现状）：

| 函数（**改动前**） | 代码行（去 docstring/注释） | 完全相同行 | AST 去名后同形 | 判读 |
|---|---|---|---|---|
| `_resolve_download` | 7 / 7 | **7** | **是** | **真抄**（一个字符不差） |
| `_restore_snapshot` | 21 / 26 | 16 | 否 | 前 16 行真抄 + 后 5/9 行是两种组织方式 |

| 函数（**改动后**） | 代码行 | 完全相同行 | 判读 |
|---|---|---|---|
| `_resolve_download` | 3 / 3 | 3 | 只剩一句转发（壳） |
| `_restore_snapshot` | 5 / 5 | 5 | 只剩一句转发（壳）+ 各自的遍历 |

全量对下来（**改动前** 14 个同名函数 / 145 行相同，**改动后** 15 个 / 132 行相同，
因为 `_snapshot_pairs` 是本单新加的「遍历」方法、两处形状不同）：**AST 同形的改动前有
7 个**——`_resolve_download`、`_retry_state`、`state`、`error`、`cancel`（三个单行取值器）、
`to_dict`、`from_dict`。本单只动其中 **1 个 + 1 段**，**剩下 6 个同形对是故意不动的**：

- `state` / `error` / `cancel` 是**单行取值器**（`return self._x`），抽出去只剩「多一层间接」，
  收益为负；它们是**公开状态面契约**（`TaskRetryMixin` 与前端字段），形状一致是**要求**而非重复；
- `to_dict` / `from_dict` 是 `_PartState` 的**数据形状**（两文件各一份 dataclass）。
  它是「条目库原语」那条账（`entry_store` 先例：参数化劣于清晰重复），动它要连带快照兼容、
  `dest` 字段语义与两处 dataclass 的合并——**明确不在本单**（备注第一节）；
- `_retry_state` 是 `TaskRetryMixin` 的取值入口，规则本来就在 `task_retry` 一处。

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
   `test_resume_rejects_tampered_local_file`）、materials 侧 **47 passed**
   （原始输出 `verify-11-guard-strength.txt`）。**同一段逻辑，一处有人看、一处没人看**，
   而且它今天就在仓库里。本单因此顺手把 materials 侧那条判据补上（补完那一格转红）。
2. **契约面**：`_resolve_download` 是**注入缝的解析器**（工单 10 第七节点名要回答的那个判据问题），
   两份各写一遍 = 同一个契约有两个实现、一个判据
   （`tests/test_full_task.py:199` / `tests/test_materials_task.py:252` 各查自己那一侧）。

### 三、缝划在哪（这是本单唯一有技术风险的决定）

- `_resolve_download`：解析顺序收**共享件**（`resolve_task_download`），
  **方法壳留在各自类上**——因为 `download_and_verify(resolve=self._resolve_download)` 与既有判据
  `task._resolve_download()` 都按**方法**取用；收成「基类方法」会动到类层次（工单 10 第七节
  担心的正是这个）。壳只剩一句转发 = 调用点与判据面零改动。
  **壳不是「同形重复」**：它不含规则（评审指出第一版 docstring 把它类比 `_retry_state` 是**假先例**，
  已改——`_retry_state` 是 mixin 的 `NotImplementedError` 钩子，子类返回**自己**的值对象，
  并不是「把共享规则转发出去」）。
- `_restore_snapshot`：只收**逐卷恢复**（对卷的字段做三件事：哈希不认就跳过 / 认了就把
  `ok` / `dest` / `downloaded_bytes` 一起恢复）；`iter_parts` 由调用点给
  （`_snapshot_pairs`：扁平表一行 vs 「批次 → 卷」两层）。**不引入一组回调参数**——
  只有一个「怎么遍历」的入参，形状差异留在各链路的 `_snapshot_pairs` 里可见。
- 两条链路的 `_restore_snapshot` / `_resolve_download` 体量都是「**一句转发**」，
  这是可机检的（见第五节守卫第 2 条）。

## 验收记录（2026-09-13）

### 一、先量再动（量具落盘、可复跑）

| 量具 | 命令 | 结论 |
|---|---|---|
| `measure-11-duplication.py` | `python .scratch/resumable-download/measure-11-duplication.py` | 改动前：`_resolve_download` 7/7 逐字相同、AST 同形；`_restore_snapshot` 21/26、相同 16、AST 不同形。改动后：两处各 3 / 5 行代码、AST 同形（都是壳） |
| `measure-11-surface.py` | `python .scratch/resumable-download/measure-11-surface.py` | 改动前：14 个同名函数 / 145 行相同 / **AST 同形 7 个**；改动后：15 个 / 132 行 / **8 个**（含收后的两处壳）。本单只动其中 1 个 + 1 段 |
| `probe-11-resolve-seam.py` | `python .scratch/resumable-download/probe-11-resolve-seam.py` | 注入缝四格 + 卷级恢复五格，总判 PASS（落盘 `verify-11-resolve-seam.txt`） |
| `run-11-suite.py` | `python .scratch/resumable-download/run-11-suite.py 120` | 逐文件全套：196 文件 / 绿 196 / 红 0 / 卡住 0（落盘 `verify-11-suite.txt`） |

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
| `_restore_snapshot` 去掉哈希校验（full） | **红**（收工之后复跑，仍红） | `test_full_task.py::test_resume_rejects_tampered_local_file` |
| `_restore_snapshot` 去掉哈希校验（materials） | **补判据前：绿（判据无效）**；**本单补上 materials 侧那条判据后：红** | `test_materials_task.py::test_apply_task_rejects_tampered_local_file` |
| `_resolve_download` 只认实例属性 | **红** | `test_full_task.py::test_apply_starts_and_status_reports_progress` |
| `_resolve_download` 永远返回缺省实现 | 整支跑会因为真下载器取不到真 url 卡在退避里 → 探针如实记「探针失效」；**逐文件隔离**后 full 侧 `test_full_task.py` 19 failed / `test_full_apply.py` 2 failed（红是真的） | `verify-11-guard-strength.txt` 末尾的隔离记录 |

### 四、做了什么（改动清单）

| 文件 | 变化 |
|---|---|
| `src/contest_generator/task_download.py` | 新增 `resolve_task_download(task)` 与 `restore_snapshot_parts(snapshot_path, iter_parts)`；docstring 补「本模块还持哪几件任务层共享事」 |
| `src/contest_generator/full_task.py` | `_resolve_download` 18 → **3 行代码 / 1 句转发**；`_restore_snapshot` 21 → **5 行代码 / 1 句转发**；新增 `_snapshot_pairs`（扁平分卷表遍历，一行）；`download_resume.file_sha256` 调用点随之内联走 |
| `src/contest_generator/materials_task.py` | 同上（materials 侧 `_snapshot_pairs` 是「批次 → 卷」两层遍历） |
| `tests/test_download_sequence_home.py` | +2 用例：共享件守卫（形状 + **壳只许一句**，含**两段阳性对照**）+ 反向注入验证（抄回胖身必须转红） |
| `tests/test_materials_task.py` | +1 用例：补 materials 侧缺掉的哈希校验判据（与 full 侧对偶）；**顺手修掉 `_fake_download` 缺 `dest.parent.mkdir`** 那个潜伏缺陷（见第五节第 6 条） |
| `tests/test_task_download.py` | +10 用例：两个新共享件自己的行为契约（含大小写不敏感、**非 Mapping 存档项按跳过**） |
| `.scratch/resumable-download/measure-11-duplication.py` / `measure-11-surface.py` | 量具（两个时刻：`git show` + 现状，可复跑） |
| `.scratch/resumable-download/probe-11-resolve-seam.py` / `probe-11-guard-strength.py` / `run-11-suite.py` / `run-11-evidence.py` | 探针与跑法（证据由脚本落盘成 UTF-8，不走 shell 重定向） |
| `.scratch/resumable-download/verify-11-*.txt` | 证据（resolve-seam / guard-strength / 逐文件全套） |

### 五、双轴评审结论（2026-09-13，两轴独立跑）

**Standards 轴**（8 条）与 **Spec 轴**（8 条）各自独立跑；**逐条落地如下**：

| # | 轴 | 问题 | 处置 |
|---|---|---|---|
| 1 | Spec | 第五节（评审结论）未填就挂着 `resolved` | 本节的表就是它；`resolved` 与内容一致了 |
| 2 | Spec | 第三节引「`verify-11-guard-strength.txt` 末尾的隔离记录」，而该文件当时**没有**这段（落盘是 UTF-16，转 UTF-8 时把追加段弄坏了） | 隔离记录**写进 `run-11-evidence.py`** 由脚本落盘，三个证据文件全部 UTF-8 重新生成；本节第 3 条与文件对得上 |
| 3 | Standards | 工单「改动清单」写的 `_saved_parts_of_batch` **不存在**，行数（3 行）也与实际不符 | 改成实际形状（`_snapshot_pairs` + 一句转发），行数按量具口径重写 |
| 4 | Standards | `SavedItemLike` 是**死代码**（零引用，实现按 `isinstance(saved, Mapping)` 判） | 删掉 |
| 5 | Standards | `_saved_parts_of_flat_table` 是**纯中间人**（一个调用点、零判据），而 materials 侧同款是内联的 | 内联进 `_snapshot_pairs`，两侧形状对称 |
| 6 | Standards | 三处 docstring 把壳类比 `_retry_state` 是**假先例**（那不是壳，是 mixin 的 `NotImplementedError` 钩子） | 三处改成真理由（调用点 + 既有判据按方法取用），并写明「壳不含规则，不算同形重复」 |
| 7 | Standards | 守卫第一版是**形状缺席**判据，漏了「先调共享件、再把规则抄一半」这种**半抄** | 加 `_fat_shell_bodies`（壳里只许 1 句、且必须是转发）+ **第二段阳性对照**（半抄样例） |
| 8 | Standards | 类型注解风格不一（`collections.abc` 与 `typing` 混用；仓内 `typing` 72 处 vs `collections.abc` 13 处） | 注解统一走 `typing`，只留 `collections.abc.Mapping`（**运行时 `isinstance` 用**，不是注解） |
| 9 | Standards | 新用例把四条判据塞进一个循环 | 保留（同族形状用一个参数化循环是既有风格，且失败信息带上了具体形状），但把**非 Mapping**那一格单独抽成一条用例（见下） |
| 10 | Spec | 「零行为变化」有一处**不成立**：存档项不是字典时，旧码靠 `AttributeError` 撞进 `except Exception`（**恰好**也是跳过），新码按 `isinstance(Mapping)` 判形状 | 承认为**行为差异**并在工单写明：结果相同（跳过），但不再借异常控制流；**补一条判据**（`test_restore_snapshot_parts_skips_non_mapping_entries`）把它钉住 |
| 11 | Spec | `measure-11-surface.py` 的口径是**现状**，工单同时引用了「改动前 14 个/145 行」与「改动后 15 个/132 行」两组数 | 第一节改成两张表（改动前 / 改动后），数字全部由量具当场打印 |
| 12 | Spec | 工单说「AST 同形只有 7 个」但未列名，读者无法判边界 | 第一节列名（7 个改动前 / 8 个改动后含收后的两处），并逐类写明「为什么不动剩下的」 |
| 13 | Spec | 评审复核确认的**真**结论（无需改） | `iter_parts` 不是投机泛化（两种遍历都真实存在且都被跑到）；`tests/` 既有文件 0 deletions（4 处删除 = 一个 import 搬家 + 一条 docstring 换行）；改动前后求值顺序、短路、`file_sha256` 调用次数、`part.sha256` 空值、`.lower()` 逐条等价 |
| 14 | 两轴 | **评审自己撞出的一个潜伏缺陷**：`tests/test_materials_task.py::_fake_download` 不建父目录 → 它写的文件**从来没落到任务目录**（真下载器会建目录，假件不建），而按调用次数 / 状态的断言照样绿 | 补 `dest.parent.mkdir(parents=True, exist_ok=True)`，并在助手上写明这是被本单新判据照出来的（不建目录的假件会让「盘上有没有那份」永远为假） |

**这轮评审值在哪**：第 10 条是**唯一真实的行为差异**（原来是异常兜底、现在是形状判定），
第 7 条是**守卫比工单承诺的弱**（半抄不红），第 6 条是**假先例**（引了一个并不存在的模式），
第 14 条是**判据自己踩到的假形状**——四条都属于「全绿、探针 PASS 也照样存在的错」，
只有把正文逐行摆开、把守卫反向注入才看得出来。

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
- **别把「壳」当成重复**（评审纠正过一次）：`_resolve_download` / `_restore_snapshot` /
  `_retry_state` 这类「类上一句转发」不含规则，规则在共享件里；守卫据此数**语句数**，
  而不是禁止同名方法出现。
- 与工单 09 兼容别名的清理仍是**两件事**（那条是「名字有两个住处」）。
