# 15 — 12 键状态载荷契约的第三份副本：量清各份的强度与覆盖面，再决定缝划在哪

**要做什么：** 工单 12 把「状态载荷键集合」在 `tests/test_download_status_surface.py` 收成了
一份常量 `STATUS_KEYS`（12 个键、**严格相等**断言），但**仓内还有字面副本**——
`tests/test_full_task.py::test_status_idle_shape` 里那一片 `set(...) == {12 个字面键名}`。
工单 12 评审第 17 条**明文没收**它：收它要改第二个既有文件、扩那一单的改动面。
本单把这笔账还掉：**先量、再判、再决定收不收**。

**被谁阻塞：** 无——可立即开始。工单 12 已 resolved（`4fc27282`），其评审第 17 条
与备注末条就是本单的出处。

**状态：** resolved（**处置 = 收**：测试侧共用一份常量 + 新增单一家结构守卫；**产品侧热路径一字节未动**）

- [x] **先量再动**：逐份建表（位置 / 形状 / 断言强度 / 覆盖哪一侧 / 哪一态 / 端点用例跑到没跑到）+
      `_RETRY_FIELDS` 重叠面；量具落盘可复跑（基线 `git show 0344eb61`，扫描面显式写明）。
      见「一」。
- [x] **判据强度**（错版注入、每格自证注入生效、卡住如实记）：7 格 + **before / after 两版对照**
      （基线那一版用 `git worktree` 检出跑同一支探针，可复跑）。见「二」。
- [x] **答清「收成一份之后覆盖面会不会缩水」**：逐格比过——**只差一格**，且差的那一格是
      「触发次数」不是「载荷覆盖」；`test_status_idle_shape` 的**取值**那半是独有覆盖，留住了。
      见「二」第 3 条与「三」。
- [x] **决定缝划在哪**：收 = **测试侧共用一份常量**（`from tests.test_download_status_surface import
      STATUS_KEYS`，仓内先例 4 处）；**不动产品侧投影**——没有「漏一边就出 bug」的证据（见「三」）。
- [x] **零行为变化**：既有断言只换期望值的来源、行为断言一条未删；`git diff --numstat tests/` 的
      15 行删除**逐行**列出；相关 85 passed；逐文件全套 **196 文件 / 绿 196 / 红 0 / 卡住 0**。见「四」。
- [x] 双轴评审（Standards / Spec 各自独立跑，用 `code-review` skill）；判定与逐条处置见「五」。

## 口径与纪律（承自工单 09/10/11/12）

- 改动前那份**从 `git show <改动前提交>:<文件>` 取**，不读工作区现状。
- 跑测试一律 `python -m pytest`；逐文件套跑用 `run-11-suite.py 120`（单条全套在本机间歇性卡死）。
- 证据文件落 **UTF-8**、由脚本落盘（模板 `run-12-evidence.py`），别用 shell 重定向。
- 工单 / 提交信息一律中文。

## 初查线索（开工前 10 分钟的粗扫，**待正式量具复核**，别当结论）

粗扫看到的候选（**要按量具口径逐份落实，别照抄这张表**）：

| # | 位置 | 形状 | 粗判强度 | 粗判覆盖面 |
|---|---|---|---|---|
| ① | `tests/test_download_status_surface.py`（`EXISTING_KEYS` / `NEW_KEYS` → `STATUS_KEYS`） | 常量集合 | `==`（严格） | 两侧 × 空态 + 有态；另有端点用例 |
| ② | `tests/test_full_task.py::test_status_idle_shape` | **内联 12 个字面键名** | `==`（严格） | **只有 full 侧 × 空态** |
| ③ | `tests/js/*.test.mjs` 的前端 fixture（`fullStatus()` 之类） | 造输入的假载荷 | **只读不判**（不是断言） | 前端渲染用例的输入 |

另有 `_RETRY_FIELDS`（`test_download_status_surface.py`）——粗看是**另一件事**的字段集
（重试观测的六个字段，含**不载荷**的 `last_error_kind` / `last_retry_at`），
与 12 键契约只是**部分名字重合**；重叠面与语义关系要在量具里量清楚再判，
**别拿「名字像」当成「同一份契约」**。

---

## 验收记录（2026-09-13）

### 一、先量再动：12 键契约在仓内一共几份、各在哪、各断言到什么强度

量具 = `.scratch/resumable-download/measure-15-status-key-copies.py`，
命令 `python .scratch/resumable-download/measure-15-status-key-copies.py 0344eb61`，
证据 = `verify-15-duplication.txt`（改动前那一份走 `git show <ref>:<文件>`，重排后可复跑）。

**契约本体从产品侧投影现算**（量具不自带第 N 份副本）：两侧各 **12** 键、逐字相同。

**扫描面（写下来，别藏）**：产品侧投影 2 个文件、测试 3 个文件、前端 fixture 3 个 `.mjs`
（量具 A 节自认「**不搜全仓**，按『状态载荷键会出现在哪些地方』逐个点名」）；
**另加 F 节做全 `tests/` 树扫描兜底**——回答「一共几份」不能只靠点名。

| # | 位置 | 形状 | 断言强度 | 覆盖侧 | 覆盖态 | 端点用例跑到它吗 |
|---|---|---|---|---|---|---|
| ① | `tests/test_download_status_surface.py:42` `STATUS_KEYS`（= `EXISTING_KEYS`(8) \| `NEW_KEYS`(4)） | 常量（**联合**） | `==` **严格** | full + materials | **空态 + 有态** | **是**：`test_endpoints_expose_new_fields` 两个端点都断言 `set(body) == STATUS_KEYS` |
| ② | `tests/test_full_task.py::test_status_idle_shape`（内联 12 键） | 内联字面 | `==` **严格** | **只有 full** | **只有空态** | **否**（直调 `full_task_status(None)`；另 3 个端点用例不断言键集合） |
| ③ | 产品侧两侧投影（各 2 个 `return {...}`：空态 / 有态） | **实现**，不是副本 | 被 ①② 判 | full / materials | 空态 + 有态 | 间接（端点用例读的就是它们） |
| ④ | `tests/js/*.test.mjs` 共 **21 处**对象字面量 | 造输入 | **只读不判** | —— | —— | 否（渲染用例的输入） |

- **F 节（全树）**：收口前命中 **2 个文件**（home 的 8 键 / 12 键两份 + `test_full_task.py:677` 的 12 键内联）；
  **收口后 1 个文件**（只剩 home）。
- **`_RETRY_FIELDS`（6 个）**：与契约**名字**交集 **4**（`retry_count` / `retrying` / `resume_percent` /
  `message`）；另外两个是**内部属性名**——`last_error_kind` 对应**载荷键 `error_kind`**、
  `last_retry_at` **根本不进载荷**。→ 它是「重试观测」那件事的字段集，**不是契约副本**
  （重叠 4 < 阈值 8）。判据单源在 `tests/test_download_status_surface.py` 的 `_RETRY_FIELDS`。
- **「哪几份会被哪个端点测试真的跑到」**（量具 D 节**机械判定**，不是人读）：
  | 端点用例 | 打的端点 | 断言键集合？ |
  |---|---|---|
  | `test_download_status_surface.py::test_endpoints_expose_new_fields` | 两个 status 端点 | **是** → 用 **`STATUS_KEYS`** |
  | `test_full_task.py::test_apply_starts_and_status_reports_progress` | `/api/update/full/status` | 否（只读几个字段值）→ 不依赖任何副本 |
  | `test_full_task.py::test_status_idle_before_any_task` | 同上 | 否 |
  | `test_materials_task.py::test_status_endpoint_idle` | `/api/update/materials/status` | 否 |

### 二、判据强度：逐格 before / after（配对证据）

探针 = `.scratch/resumable-download/probe-15-guard-strength.py`（逐文件跑、每格先**自证注入生效**）。
错版一律**包装真实现、只扰动要测的那一处**（`_orig(task)` 走真实现，再对返回的 dict 做一件事）——
第一版把整支投影抄成错版，非目标分支只能填桩，大量用例因桩而红，「红在谁身上」直接失效。
「收之前」那一版 = `run-15-evidence.py before`：**`git worktree` 检出基线 `0344eb61`**、把同一支探针
拿过去跑（可复跑）。

| 格 | `test_download_status_surface.py`（常量侧） | `test_full_task.py`（原字面副本侧） | `test_materials_task.py` |
|---|---|---|---|
| `full:add_key`（两侧都多一个键） | 红 2 failed（`contracted_set[full]`、`endpoints`）｜**前/后同** | 红 1 failed（`test_status_idle_shape`）｜**前/后同** | —— |
| `full:idle_add_key`（只在空态多键） | 红 2 failed｜前/后同 | 红 1 failed｜前/后同 | —— |
| `full:drop_key`（少一个键） | 红 5 failed｜前/后同 | 红 3 failed｜前/后同 | —— |
| `materials:drop_key`（另一侧少键） | 红 3 failed｜前/后同 | —— | **绿**（那侧本来就没有副本；靠常量侧的 `[materials]` 参数化兜住） |
| `full:rename_key`（键名改错） | 红 3 failed｜前/后同 | 红 2 failed｜前/后同 | —— |
| `full:idle_total_bytes`（**只改取值**） | **绿**（30 → 32 passed）｜前/后同 | **红 1 failed**｜前/后同 | —— |
| `full:add_key_together`（产品 + 常量一起改 = **按手续加字段**） | 绿｜**已从探针撤出**，见下 | 前：**红**；后：**绿** | —— |

**三条结论（这就是取舍的全部数据）**：

> 读表口径：`前/后同` 指**红的是哪几条用例、各有几条**前后一致；`passed` 数在
> `test_download_status_surface.py` 上会 +2（本单新增两条守卫用例），那不是覆盖差异。

1. **键 × 侧 × 态：收口没有削掉任何一格覆盖**。七格里六格前/后逐格相同——包括另一侧
   （`materials:drop_key`）与空态（`full:idle_add_key`）：那份内联字面在「(侧, 态) × 键集合」
   这一面上**没有一格是它独有的**。
2. **取值那半是它独有的，必须留**：只改空态 `total_bytes`（键集合不变）时，
   常量侧**绿**、只有 `test_status_idle_shape` **红**。故本单**只换键集合的来源**，
   三行取值断言（`state` / `parts` / `total_bytes`）**一字未动**。
3. **唯一变化的一格 =「按手续加字段」的触发次数**：收口前它会拦住「产品两侧加键 + 把
   `STATUS_KEYS` 的来源 `NEW_KEYS` 也补上」这套手续（`test_full_task.py` 红 1 failed），
   收口后不再拦。**这一格改用真源码编辑量**（运行时改常量已无法忠实模拟：新守卫把
   「内存里的 `STATUS_KEYS`」与「源码里的契约」绑在一起，运行时改会被守卫读成自相矛盾）——
   量法 = `run-15-evidence.py together`（临时 worktree 里真改 4 处产品载荷 + 1 处常量来源），
   证据 `verify-15-together.txt`：
   - **基线**（内联副本还在）：**`1 failed`**（`test_status_idle_shape`）；
   - **现状**（已收口）：**`65 passed`**。
   即：那一格拦的正是**加字段的规定手续**（`test_status_keys_are_the_contracted_set` 的
   docstring 写明「改契约就该改这一处」）——两份副本并存时，按手续改完还会在另一个文件红一次。
   **判为可接受**：契约的「严格相等」拦的是「悄悄漂」（改了产品没改契约 → 常量侧必红，六格已证），
   而不是「按手续改」（那本就该放行）。

### 三、决定缝划在哪

**缝 = 测试侧共用一份常量**，`tests/test_full_task.py` 里那 12 行字面换成
`from tests.test_download_status_surface import STATUS_KEYS`（文件顶部 import 区，
紧挨既有的 `from tests._byte_server import ByteServer`）。

- **为什么不走「产品侧投影单源」**：工单 10 第三节的判据——**没有「漏一边就出 bug」的证据
  不许为对称好看动热路径**。本单量的证据恰好相反：产品侧两侧投影的键现在由
  `test_status_keys_are_the_contracted_set` **在空态与有态上都查**，探针 `full:add_key` /
  `materials:drop_key` 两侧**各自都红**——没有「一侧有人看、一侧没人看」的不对称；
  产品侧那 4 份键表是**实现**（空态 / 有态各一份），不是契约副本。
  → **热路径一字节未动**（`git status` 只有两个测试文件）。
- **测试模块互相 import 有先例**：`from tests.test_impact import _sse_events`（4 处：
  `test_deepen.py` / `test_params.py` / `test_revision.py` / `test_task_progress.py`）、
  `from tests.test_update_app import _load_update_app`；**无环**（全仓 `from tests.test_full_task`
  0 命中），与收集顺序无关（模块级常量在用例执行前已绑定）。
- **新增一条结构守卫**（`test_status_contract_has_a_single_home`）钉「别又抄回来」：
  扫 `tests/**/*.py`，判据 = **字面集合或其联合**枚举契约 ≥8 个键；只许住在契约的家文件里。
  配 `test_contract_home_guard_turns_red_on_a_second_copy`：阳性对照（12 键字面副本）、
  阳性对照（`A | B` **联合**副本）、阴性对照（4 键的部分重叠不误伤），
  假副本的键**从契约现 derive**（不写死 12——写死就等于让守卫跟着数字走，正是本单批评过的毛病）。
- **守卫的两道取证**（缺一不可）：
  - **反向验证**（上面的用例，喂 `%TEMP%` 副本，真身不碰）；
  - **真身实测**（`run-15-evidence.py real-tree`，脚本化可复跑）：往 `tests/` 真放一份第二副本
    → 守卫**红**并指名 `_tmp_second_copy.py:2（12 个契约键）` → 删掉 → **32 passed**；
    `git status --short tests/` 只剩本单改的那两个文件。
    *第一版这道实测**没红**：副本是 PowerShell 写的（带 BOM），`ast.parse` 抛 `SyntaxError`
    而守卫 `except SyntaxError: continue` **静默跳过**——「守卫只是装饰」当场现形。
    已改成 BOM 用 `utf-8-sig` 吃掉、读不了 / 解析不了一律大声红。*
- **JS 侧那 21 处对象字面量不动**：它们是渲染用例的**输入**（只读不判），
  每个用例只造它要渲染的那几个字段；逼它们写全 12 键是噪声。守卫面因此只含 `tests/**/*.py`。

### 四、「零行为变化」逐条对过

| # | 关注点 | 来源 | 结论 |
|---|---|---|---|
| 1 | `git diff --numstat tests/` | diff | `188 0`（`test_download_status_surface.py`：守卫 + 三条反向验证，**纯新增**；评审整改后又加厚了）与 `10 15`（`test_full_task.py`） |
| 2 | 那 **15 行删除**逐行是什么 | `git diff -U0` | ① 1 行旧注释（`# 八个既有字段（前端契约，不许改名）…`）；② 1 行 `assert set(status) == {`；③ **12 行键名字面量**；④ 1 行 `}`。**全部是被替换掉的那份内联副本本身** |
| 3 | 有没有**行为断言**被删 | 读码 | **没有**：`assert set(status) == {…}` → `assert set(status) == STATUS_KEYS`（同一条断言，期望值改走单源）；同处 3 行取值范围断言（`state` / `parts` / `total_bytes`）**一字未动**；该用例其余部分零改动 |
| 4 | 新增的 10 行是什么 | diff | 1 行 import + 8 行注释（写明「为什么不再抄一遍 / 取值断言为什么留 / 唯一差别是那一格的触发次数」）+ 1 行改后的断言 |
| 5 | 相关用例 | 判据 | `pytest tests/test_download_status_surface.py tests/test_full_task.py tests/test_materials_task.py` → **85 passed**（改动前 83；+2 = 两条新守卫用例） |
| 6 | 逐文件全套 | 判据 | `python .scratch/resumable-download/run-11-suite.py 120` → **文件 196：绿 196 / 红 0 / 卡住 0**（326.8s，落盘 `verify-15-suite.txt`） |
| 7 | 产品行为 | 读码 + diff | 产品侧（`full_task.py` / `materials_task.py` / 载荷键）**零改动**——本单只动测试与 `.scratch` 工具 |
| 8 | 端点载荷 | 判据 | 两个 status 端点的键集合断言（`test_endpoints_expose_new_fields`）逐字未改 |

### 五、双轴评审结论（2026-09-13，两轴各自独立跑）

| # | 轴 | 问题 | 处置 |
|---|---|---|---|
| 1 | **Spec** | **「覆盖面严格包含本处」这句在「按手续加字段」那一格为假**——原注释把因果说反了（那格恰恰证明收口前它是唯一能把该情形拦下的） | **当场改**：注释与守卫 docstring 都改成实测口径——「键 × 侧 × 态**没有一格独有**；唯一差别是那一格的**触发次数**」，并附两版实测（基线 1 failed / 现状 65 passed） |
| 2 | **Spec** | 「哪几份会被哪个端点测试真的跑到」**没被回答**（原 D 节只印端点用例名） | **当场改**：量具 D 节改成**机械判定**（端点用例里有没有契约相交的集合断言 → 用到哪一份）；答案见「一」末表 |
| 3 | **Standards** | 守卫**自证名不副实**：现状只命中 `EXISTING_KEYS`（8 键），不是契约本体 | **当场改**：补**联合解析**（`A | B` + 模块级名字），自证改成「本文件里必须有一份 **12 键**命中」 |
| 4 | **Standards** | 守卫只认 `ast.Set`，**连契约本体（联合）都认不出**——这是一条真实的绕过路径 | **当场改**（同上）；反向验证加**联合副本**那一格 |
| 5 | **Standards** | 结构守卫第一版对读不了的 `.py` **静默跳过** → 真身实测**假绿**（BOM 副本被吞） | **当场改**：`utf-8-sig` 吃 BOM；读不了 / 解析不了一律大声红；真身实测复跑转红 |
| 6 | **Standards** | 阈值理由两处措辞漂（都写「契约副本一律 ≥11」，而 `EXISTING_KEYS` 就是 8） | **已改**：守卫处写成「仓内真正的契约副本是 **8 键**（前半）与 **12 键**（联合）」 |
| 7 | **Standards** | `run_in_baseline_worktree` 把 `mkdtemp` 放在 `try` 外，`git worktree add` 失败会漏一份整仓拷贝 | **已修**：`mkdtemp` 进 try，`finally` 里连空壳目录一起 `rmtree` |
| 8 | **Standards** | 探针七格**没有一格往 `tests/` 放第二副本**——守卫的「会红」只由自带反向验证背书 | **已补**：`run-15-evidence.py real-tree` 脚本化真身实测（放副本 → 红 → 删 → 绿 + `git status` 复核） |
| 9 | **Standards** | 源码里写死产物路径（落盘器里的 `verify-15-*.txt`） | **判为不适用并写明理由**：工单 12 第 14 条管的是**产品源码 docstring**；这两处是**落盘器自己的输出文件名**（它就是那三个文件的产出者，文件名是它的输出契约）。**本单没有改任何产品源码** |
| 10 | **Standards** | UTF-16 残留：`_tmp15.txt` / `_tmp15-full.txt`（BOM `FF FE`） | **已删**。如实记：那是我自己用 PowerShell `>` 重定向造的——正是工单纪律点名禁止的形状（证据一律由脚本以 UTF-8 落盘） |
| 11 | **Standards** | `CONST_PLUGIN` 的注释与输出对不上（描述的是已修掉的失真版） | **已修**：注释写实；并**把那一格从探针撤出**——运行时改常量无法忠实模拟「按手续加字段」（新守卫把内存常量与源码绑在一起），改用 worktree 真源码编辑（`verify-15-together.txt`） |
| 12 | **Spec** | 「只允许新增」与「既有用例被改」字面冲突（实测 15 行删除） | **如实记为不成立**：确有 15 行删除，全部是**被替换掉的那份内联副本本身**，行为断言等价保留（「四」第 2、3 条逐行列了）。与工单 12 评审第 7 条同款处置：改口径不缺口径 |
| 13 | Spec / Standards | 独立复跑确认「无问题」的三项 | 记录：测试互 import 有先例且无环；守卫会红（12 键副本被指名、4 键阴性对照不误伤）；三支脚本不会重演工单 14 的 GBK 崩溃（`PYTHONIOENCODING` 与 `stdout.reconfigure` 都在）；新脚本与工单 12/14 的同形度未到该抽的程度（共用只有「子进程 + UTF-8 落盘」骨架） |

**这轮评审值在哪**：第 1 条是**「自己写的取舍说明与实测对不上」**（我写了「严格包含」，
而逐格一比就知道那一格是它独有的触发）——如果只凭那句话收单，下一个人读到的就是错的账；
第 3、4、5 条是**守卫自己有两处洞**（认不出联合 → 连契约本体都认不出；静默跳过 → 真身实测假绿），
两条都属于「全绿也算错」；第 8 条是**判据的证据链缺一环**（守卫的红只在 tmp 目录里证过）。

## 备注

- **本单的边界（别读大）**：
  - **产品侧一字节未动**（两侧投影、载荷键、端点全部原样）——缝划在测试侧；
  - 不动 JS 侧那 21 处对象字面量（渲染用例的输入，只读不判）；
  - 不动 `_RETRY_FIELDS`（它与契约只重叠 4 个名字，是「重试观测」那件事的字段集）；
  - 不动 `test_status_idle_shape` 的**取值**断言（探针证过那是它独有的覆盖）。
- **与工单 14 的分工**：14 是「一个公开导出还有没有活口」的判定单（结论 wontfix，只落 docstring
  与 spec 更正）；本单是「同一份契约有几份副本」的收口单（动两个测试文件 + 一条新守卫）。
  两单不共享改动面，各自可评审。
- **将来要加字段怎么办**（本单之后的手续，只有一处）：改
  `tests/test_download_status_surface.py` 的 `STATUS_KEYS`（或其来源 `EXISTING_KEYS` / `NEW_KEYS`）
  ——产品侧改完而契约没改会红（六格已证），契约改完则两处测试一并跟上
  （`verify-15-together.txt` 的「现状」那一版：**65 passed**）。
  若哪天两侧**依法**要长得不一样，就在那条用例里显式分成两套键集合（让不对称成为写下来的决定）。
- **推翻本单要先跑**：`measure-15-status-key-copies.py`（几份副本、各什么强度）、
  `probe-15-guard-strength.py`（各格红不红）、`run-15-evidence.py before|together|real-tree`
  （三份两版/真身对照证据）。**「探针自己栽过」的六处**（工单 13 记了四次、工单 14 两次、
  本单两次：包装式错版、运行时改常量的假象）都写在各自的脚本注释里。
