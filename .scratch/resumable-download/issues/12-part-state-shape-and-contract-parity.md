# 12 — `_PartState` 形状：四处「同形重复」里唯一值得动的一处（两处从未执行的 `from_dict` + 两侧契约判据不等强）

**要做什么：** 让「分卷状态形状」这条契约**只留它真正被用到的部分**，并把守卫从「弱的那一侧」
拉齐到「强的那一侧」：

1. 删掉**两处从未被执行的** `from_dict`（`full_task._PartState.from_dict`、
   `materials_task._PartState.from_dict`）与 `materials_task._BatchState.from_dict`——
   三个定义，零调用点（工单 12 的静态 + 运行时 + 错版炸弹三重取证，见「先说清代价」第二节）；
2. `tests/test_download_status_surface.py` 的**两侧契约断言拉齐**：`full_task_status` 一侧
   早就是 `set(...) == 12 个键`（严格），两侧共用的那条却是 `<= 子集`（弱）；
   两条都改成**严格等于**同一份键集合（收成 `STATUS_KEYS`）——**多一个键与少一个键同等致命**
   （前端零分支契约：少一个键 → `undefined`；多一个键 → 前端拿不到它，而契约测试是绿的）；
3. 新增**一条结构守卫**（钉「形状有没有再漂」）：两条链路的 `_PartState` 在
   **字段 / 默认值 / 方法集合 / `to_dict` 正文 / `to_dict` 键序**五个轴上逐项相同，
   且字段序列 == 快照契约；`from_dict` 这类「一侧多长出来一个方法」正是它要抓的漂移；
4. **不合并两个 dataclass**：形状今天由 `task_download.PartLike` 协议与
   `restore_snapshot_parts` 兜着，字段逐个相同**从来没付出过代价**（见「先说清代价」第三节）。

**被谁阻塞：** 无——工单 11 已 resolved（`ea0ae09d`），其备注第一节明文把 `_PartState`
留作另立单；工单 13（同形重复盘点）量出来的账里，**只有这一处值得动代码**。

**状态：** resolved

- [x] **先量再动**：量具 `measure-12-twin-candidates.py` 对 12 对同名函数全量量过
      （代码行 / 逐行相同 / AST 同形 / 语句同形 / 数据形状逐字段 / 两文件同提交次数），
      基线取 `git show 5461f39d`，所以重排后仍可复现；`from_dict` 的**零调用点**另有
      静态（全仓 grep + 测试目录 grep）与运行时（三处换成抛异常的炸弹 → **改动前** 81 passed）
      两手取证。
- [x] 删掉三处 `from_dict`；**快照落盘形状一个字节不变**（`to_dict` 未动，
      `ok` / `dest` / `downloaded_bytes` 三个字段仍在 JSON 里）。
- [x] 两侧契约断言拉齐成**严格等于**（工单 04 定的 12 个键即现状，本单只把弱的那条改严）。
- [x] 新增形状守卫 + **反向验证**：三条阳性对照（一侧加回 `from_dict` / 一侧漏 `dest` /
      一侧改 `to_dict` 键名）都必须被认出来；另做一次**面向真身源码**的反向验证
      （临时改真身 + 断言转红 + 当场恢复，见验收记录第三节）。
- [x] **零行为变化**：既有判据全程绿（逐文件全套 **196 文件 / 绿 196 / 红 0 / 卡住 0**）；
      `git diff --numstat tests/` = **199 插入 / 7 删除**——那 7 行全部是**被本单替换掉的
      旧断言、旧测试名与旧 docstring**（逐行清单见验收记录第五节第 4 条），
      既有**行为**断言一条未改。
- [x] 双轴评审（Standards / Spec 各自独立跑，两轴共 17 条逐条落地）；判定记进「验收记录」。

## 先说清代价（为什么这一单成立、边界在哪）

### 一、四类候选的账（量出来的，不是读出来的）

`.scratch/resumable-download/measure-12-twin-candidates.py`（基线 `git show 5461f39d`）：

| 候选 | 代码行 full/mats | 逐行相同 | AST 同形 | 判读 | 本单 |
|---|---|---|---|---|---|
| ① `full_task_status` / `task_status` | 45 / 45 | **43** | 否（签名 + 枚举） | 长得像：真正不同的只有「卷怎么枚举」2 行 | 不动（工单 13） |
| ② `run()` | 45 / 43 | 38 | 否 | 长得像：循环形状 + `on_complete` 契约不同 | 不动（工单 13） |
| ② `_write_snapshot` | 14 / 14 | 13 | 否 | 只差封套键（`parts` vs `batches`） | 不动（工单 13） |
| ② `__init__` | 32 / 41 | 23 | 否 | 承载真实不同（单向表 vs 批次树） | 不动（工单 13） |
| ③ `to_dict` | 10 / 10 | **10** | **是** | 真抄，但**两侧都在用**（快照落盘） | 不动（合并形状无收益） |
| ③ `from_dict` | 10 / 10 | **10** | **是** | 真抄，且**两侧都没人用** | **本单删** |
| ④ `state` / `error` / `cancel` / `_retry_state` | 各 2 / 2 | 2 | 是 | 单行取值器，收益为负 | 不动（工单 13） |

### 二、`from_dict` 是**零调用点**——这才使本单成立（不是「看着重复」）

取证三手（都可复跑）：

1. **全仓 grep**：`from_dict` 的定义只有三处（`full_task._PartState`、
   `materials_task._PartState`、`materials_task._BatchState`）；消费端
   （`_write_snapshot` / `_snapshot_pairs` / `restore_snapshot_parts`）**一律直接读 dict**
   （`p["name"]` / `p.to_dict()` / `saved.get("dest")`），没有任何一处调 `from_dict`；
2. **测试目录 grep**：`tests/**` 里对 `_PartState` / `_BatchState` 的引用只有一条
   **docstring 提及**（`tests/test_task_download.py:39`），零调用；
3. **运行时取证（探针格 `from_dict_boom`）**：把三处 `from_dict` 全换成**抛异常的炸弹**，
   跑 `test_full_task.py` + `test_materials_task.py` + `test_download_status_surface.py`：
   **81 passed**（三个文件全绿，**这是本单动手之前**那三个文件的状态）。**炸弹没被碰到 =
   它们从头到尾没有执行路径**（原始输出 `.scratch/resumable-download/verify-12-guard-strength.txt`）。
   *口径*：这一格在**本单落地之后**会转红（新守卫的 `hasattr` 断言认出「有人把方法加回来」）——
   那是**期望的**，不是矛盾：死代码的证据取自改动前，改动后这条约束由守卫长期接管。

为什么这条重要：工单 11 的备注把 `_PartState` 归为「条目库原语那条账（参数化劣于清晰重复）」，
方向是把**两份合成一份**；量出来的事实是：**这两份里的乘一半（`from_dict`）根本没有执行路径**，
而 `to_dict` 两侧都在用、形状一致在今天没有任何代价。所以正确的动作不是「合并」，
而是**把没人用的那半删掉**——删的是**没有执行路径的代码**，不是热路径，
因此不受「不许为了对称好看动热路径」那条纪律约束。

### 三、为什么不合并两个 dataclass（同一条纪律的另一面）

- 两个 `_PartState` 的字段名 / 默认值 / `to_dict` 键序**逐项相同**（量具逐项打印），
  今天由 `task_download.PartLike` 协议 + `restore_snapshot_parts` 兜着（工单 10/11 的地基）；
- 合并要么把它搬进 `task_download`（任务层共享件从吃协议变成吃一个具体类），
  要么让 `full_task` 直接用 `materials_task._PartState`——两者都会让
  「共享件只吃协议」这条分层变脆，收益只是「少一份 20 行的 dataclass」；
- 历史给的证据也不一样：`_PartState` 的**字段**从来没漂过（`git log -S 'class _PartState'`
  只命中两次创建），漂的是**没人用的那半**。所以本单只删没用的，不合并形状。

## 验收记录（2026-09-13）

### 一、先量再动（量具落盘、可复跑）

| 量具 | 命令 | 结论 |
|---|---|---|
| `measure-12-twin-candidates.py` | `python .scratch/resumable-download/measure-12-twin-candidates.py 5461f39d` | 12 对同名函数全量对过；本节第一节那张表；`_PartState` 字段/默认值/两方法逐项相同 |
| `probe-12-guard-strength.py` | `python .scratch/resumable-download/probe-12-guard-strength.py` | 十格错版注入（逐文件、每格自证注入生效），落盘 `verify-12-guard-strength.txt` |
| `rerun-12-case.py` | `python .scratch/resumable-download/rerun-12-case.py <案件名> 180` | 单格复跑（诊断用：某格卡住/失效时看原始输出与 faulthandler 转储） |
| `run-11-suite.py` | `python .scratch/resumable-download/run-11-suite.py 120` | 逐文件全套：**196 文件 / 绿 196 / 红 0 / 卡住 0**（落盘 `verify-12-suite.txt`，评审落地后复跑仍是这组数） |

### 二、判据强度（错版注入，落盘 `verify-12-guard-strength.txt`）

与本单直接相关的三格（**逐文件跑、每格先自证注入生效**）：

| 错版 | 结果 | 说明 |
|---|---|---|
| `drop_field`（`_PartState.to_dict` 漏掉 `dest`） | **绿（判据无效）** | 80 passed——**既有判据不看快照形状**。这条正是本单要补的守卫：新守卫落地后，同一处漏字段会红（第五节第 2 条那次实测给出了证据） |
| `from_dict_boom`（三处 `from_dict` 换成炸弹） | **改动前：绿（81 passed）**；**本单落地后：红** | 「零调用点」的**运行时证据只对改动前的用例集成立**：炸弹没被碰到 → 三处 `from_dict` 没有执行路径。本单落地后，新守卫的 `assert not hasattr(..., "from_dict")` 会抓到这个注入——故验收记录里**不写「照样全绿」**，写「先证明它是死代码（改动前），再由新守卫接管这条约束」 |
| `part_key` / `no_retry_fields`（状态契约字段与载荷键） | **红（判据有效，两侧各自都红）** | 用于工单 13 的结论（状态视图的判据是对称的） |
| `init_drops_name` / `getter_state_const` / `getter_error_const`（本单为工单 13 的结论补的三格） | **红** | 工单 13 的表格里 `__init__` 与单行取值器那两行的「红」由此实测支持，不是推断 |

**探针自己栽过三次（都记在 `run-12-evidence.py` 的补充段里）**：① 第一版错版把「速度窗口
记账」一起丢了 → 用例在注入下空转；② 错版正文里的 `_time` 没进 `exec` 名字空间 →
`NameError` 被重试路径吞掉 → 同样空转；③ 第一版 `__init__` 错版把卷大小吞成 0 →
真下载在重试里打转（自己造的卡住），改成「卷名不解析」这种**确定性失败**的错版。
三次都是**探针失真**，不是产品行为。

### 三、改动清单

| 文件 | 变化 |
|---|---|
| `src/contest_generator/full_task.py` | 删 `_PartState.from_dict`（10 行）+ 该类 docstring 写明「为什么没有它」；`from dataclasses import dataclass` 去掉已无用的 `field` |
| `src/contest_generator/materials_task.py` | 删 `_PartState.from_dict` 与 `_BatchState.from_dict`（20 行）+ 两处 docstring 同前 |
| `src/contest_generator/task_download.py` | `restore_snapshot_parts` docstring 补一句：存档项按 `Mapping` + `.get(...)` 读，**不是**重建 `_PartState`（读侧的形状判定单源） |
| `tests/test_download_status_surface.py` | 契约断言改**严格相等**（两侧拉齐，键集合收成 `STATUS_KEYS`）+ 新增 `_dataclass_shape` / `_shape_problems`（纯函数守卫）+ `test_part_state_shape_has_a_single_contract` + `test_shape_guard_turns_red_on_drift`（三条阳性对照） |
| `.scratch/resumable-download/measure-12-twin-candidates.py` / `probe-12-guard-strength.py` / `rerun-12-case.py` / `run-12-evidence.py` | 量具 / 探针 / 单格复跑 / 证据落盘器 |
| `.scratch/resumable-download/verify-12-{duplication,guard-strength,suite}.txt` | 证据（UTF-8，由脚本落盘，不走 shell 重定向） |

### 四、守卫真的会红（两重验证）

1. **纯函数层的三条阳性对照**（`test_shape_guard_turns_red_on_drift`，喂的是**源码文本副本**，
   真身一个字节不碰）：① 一侧把 `from_dict` 加回来 → `methods` 轴不同形；
   ② 一侧漏掉 `dest` 字段 → `fields` 轴不同形；③ 一侧把 `to_dict` 的键改名 →
   `to_dict` 轴不同形。三条各自带「锚点没命中就报错」的自证（`assert renamed != text`）。
2. **面向真身源码的一次实测**（临时改、当场恢复）：
   `materials_task.py` 的 `to_dict` 键 `downloaded_bytes` → `已下载`，
   跑 `test_part_state_shape_has_a_single_contract` **转红**，失败信息指名道姓给出
   `_PartState.methods 两侧不同形`（`methods` 轴比的是**方法正文**，所以键名改一处即被抓到）；
   恢复后复跑 **2 passed**，`git diff` 只剩本单的原改动。

### 五、「零行为变化」逐条对过

先说口径：下表里**注明来源**——`判据` = 既有／新增用例真的跑过这一格；
`读码` = 逐行对照代码得出（无独立判据）；`diff` = 逐行核对改动清单。

| # | 关注点 | 来源 | 结论 |
|---|---|---|---|
| 1 | 快照落盘内容 | 判据 | `to_dict` 一个字未改：`full-task.json` 的 `parts[]` / `materials-task.json` 的 `batches[].parts[]` 键与值不变（`test_snapshot_written_and_recoverable` / `test_write_task_snapshot_roundtrip` 绿，工单 11/10 立的） |
| 2 | 快照读入路径 | 读码 | 读侧本来就走 `Mapping` + `.get(...)`（工单 11 的 `restore_snapshot_parts`，其正文一行未动），删 `from_dict` 碰不到它 |
| 3 | 公开面 | 读码 | 删的是**私有类**上的静态方法；`__all__` / 模块级导出 / 端点载荷零变化（`grep` 复核全仓无引用） |
| 4 | 测试文件里的既有断言 | diff | `git diff -U0` 逐行列出的 **7 行删除**：`def test_status_keys_are_the_contracted_eleven(...)` 1 行（改名）+ 旧断言 3 行（`assert EXISTING_KEYS <= …` / `assert NEW_KEYS <= …` / `assert set(body) == EXISTING_KEYS \| NEW_KEYS`）+ 旧 docstring 3 行；**其余既有行为断言一条未改** |
| 5 | 契约收紧的方向 | 判据 | 旧断言只查「⊆ 12 键」，新断言查「== 12 键」；两侧**今天都满足**，故是纯收紧（`test_status_keys_are_the_contracted_set` / `test_endpoints_expose_new_fields` / `test_status_idle_shape` 绿） |
| 6 | 形状守卫自身的覆盖 | 判据 | 两条新用例 + 三条阳性对照 + 一次真身实测（第五节第 2 条），且 `methods` 轴比的是**方法正文**而不只是名字 |

### 六、双轴评审结论（2026-09-13，两轴独立跑）

**Standards 轴**与 **Spec 轴**各自独立跑（Spec 轴按工单原文逐条核「声明 vs 证据」）；
**逐条落地如下**（合并两轴的发现，`轴` 列标明来自哪一轴）：

| # | 轴 | 问题 | 处置 |
|---|---|---|---|
| 1 | Standards | `_dataclass_shape` 第一版用「逐条语句 `ast.unparse`」拼 `methods`，**类/方法 docstring 也进了正文**，于是「同一份形状、两种措辞」会被判成不同形（假红） | 改成 `_without_docstrings(node)` 先规范化再 `unparse`：只比**结构与标识符**，docstring 与注释不参与 |
| 2 | Standards | `_class_node` 返回 `None` 时后续解引用会抛 `AttributeError`，失败信息不可读 | 改 `pytest.fail("源码里找不到类 …（守卫的扫描面变了？）")` |
| 3 | Standards | 反向验证第一版只断言「有 problems」，**没有阳性对照的自证**（锚点没命中时 `str.replace` 静默返回原文 → 假绿） | 每条对照加 `assert <改后文本> != <原文>`；并补第三条对照（`to_dict` 键改名） |
| 4 | Standards | `full_task.py` 删掉 `from_dict` 后 `field` 变成死导入 | 删 `field`（`dataclass` 仍用）；`materials_task.py` 的 `field` 仍被 `_BatchState.parts` 用，保留 |
| 5 | Standards | 三条 `assert not hasattr(..., "from_dict")` 与形状守卫**职责重叠** | 保留（**有意**）：它们给的是「工单 12 删掉的就是它」这条**可读的意图声明**；而且 `from_dict_boom` 那一格证明它们不是装饰——注入加回方法时**是它们先红** |
| 6 | Standards | 守卫放在 `test_download_status_surface.py`（状态面文件）里，而它守的是**快照形状** | 保留并在 docstring 写明理由：这份形状的两侧契约（`to_dict` 键序）就是状态面契约的一部分，且该文件已有 `test_retry_observation_has_a_single_home` 这类同族**结构守卫**先例 |
| 7 | Spec | 工单要求「0 deletions」严格成立吗？实测 `tests/` **7 deletions** | **如实记为不成立**：7 行逐条列在第五节第 4 条（1 行改名 + 3 行旧断言 + 3 行旧 docstring）。这里**改口径不缺口径**：既有**行为**断言一条未改，改的正是本单点名要改的那三条契约断言 |
| 8 | Spec | 工单称「三处换成炸弹 → 81 passed…炸弹没被碰到」，但新守卫落地后同一注入**会红** | **声明失真，已改**：改成「零调用点的运行时证据**只对改动前的用例集**成立（改动前 81 passed）；本单落地后这条约束由新守卫的 `hasattr` 断言接手」——第二节那张表里两行并列写明 |
| 9 | Spec | 工单承诺守卫「五轴逐项相同」，实现里 `methods` 只比**方法名**（正文没比）——「一侧改 `to_dict` 取值」不红 | 改 `methods` 为「名字 → 规范化正文」的映射，正文参与比对；轴名相应写实（第四节第 1 条 / 第五节第 6 条） |
| 10 | Standards | `test_status_keys_are_the_contracted_eleven` 名不符实（契约是 **12** 个键，docstring 也写 12） | 改名 `test_status_keys_are_the_contracted_set`（并复核全仓无旧名引用） |
| 11 | Standards | `_shape_problems` **只对 full 侧**做「字段 == 契约 / 键序 == 契约」断言，materials 侧只靠「两侧相等」间接覆盖——两侧同时改错就全绿 | 改成**两侧都查**（`for flavor, shape in (("full",…), ("materials",…))`），并写明「两侧一起漂」正是这套副本最可能的坏法 |
| 12 | Spec | 反向验证第一版只在纯函数层证明「会红」，没有对真身源码实测 | 补第五节第 2 条那次实测（临时改真身 → 转红 → 当场恢复 → `git diff` 复核） |
| 13 | Spec | `download_part` 顺手量出「零调用点」，本单没收 | 写进备注（工单 10 已把它记为「另一单」）；**不塞进本单**——它是「一个公开导出没人用」，与「两侧同形契约」不同性质 |
| 14 | Standards | 新增的源码 docstring 里写死了 `.scratch/resumable-download/verify-12-*.txt` 这类**产物路径**（对照 `docs/agents/workflow.md` Step 2「文档里别写具体路径，会很快过期」；该条按字面辖 spec，本仓另有旧例） | 三处源码 docstring 去掉路径，只留「工单 12 + 结论 + 判据在哪一侧」；证据引用留在本工单与证据文件里 |
| 15 | Spec | 工单把量具/探针/复跑器/落盘器四个脚本同时列进本单与工单 13 的证据清单（两单重复计账） | 记为本单与工单 13 **共用**的证据池（同一批工具分别回答「哪一处值得动」与「其余为什么不值得动」）；工单 13 的表述改成「与工单 12 共用」 |
| 16 | Standards | 测试里的 `_dataclass_shape` / `PART_FIELDS` 与量具 `measure-12-twin-candidates.py` 里的同名工具**同形**（本单主题正是删同形重复，却新抄一份） | **有意保留**（判为「判断题」并写明理由）：量具是 `.scratch` 下的一次性分析工具、测试是**产品侧守卫契约**（要长期演进、要能在无 `.scratch` 的环境跑）；让测试去 import 量具会把「判据」挂到分析脚本上。仓内先例 = `entry_store` 那条「参数化劣于清晰重复」 |
| 17 | Standards | 12 键契约在仓内有**第三份**副本（`tests/test_full_task.py` 的 `test_status_idle_shape` 字面集合） | **本单不收**（收它要改第二个既有文件、扩本单改动面）；记为**独立线索**，与 `download_part` 同处备注 |

**这轮评审值在哪**：第 8 条是**声明与证据不符**（新守卫落地后同一注入会红，工单却写「照样全绿」）；
第 9、11 条是**守卫比工单承诺的弱**（方法正文没比、契约只查一侧）——两条都属于「全绿也算错」；
第 1 条是「守卫因为 docstring 措辞不同而假红」（这种守卫会被人当噪声关掉）；
第 3 条是「阳性对照自己没自证」；第 7 条是「验收线写得太死、实测不成立就如实改口径」而不是把话说圆。

## 备注

- **本单的边界**（别读大）：
  - 不动 `full_task_status` / `task_status`（工单 13 已量清并关掉）；
  - 不动 `run()` / `_write_snapshot` / `__init__`（同上）；
  - 不动 `state` / `error` / `cancel` / `_retry_state`（同上）；
  - **不合并两个 `_PartState`**（第二节第三条）；
  - 不动快照文件格式（`full-task.json` / `materials-task.json` 的键与形状一个字节不改）；
  - **不动 `materials_task.download_part`**（顺手量到、但属另一类）：本单复核它的调用点是
    **0**——`tests/test_materials_task.py:26` 只 import 不调用、`test_full_task.py:820`
    只在注释里提它、`download_resume.py` 两处提到它也只是「口径与它一致」的说明。
    它是「一个公开导出没人用」= 死代码，与「两侧同形契约」不同性质（工单 10 第七节已记为
    「另一单」），留作独立线索。
- **与工单 13 的分工**：13 是判定单（量清 → 关掉四类里的三类 + 状态视图），
  零代码改动；本单是唯一动代码的那一处。两单各自可评审。
- **依赖方向**：形状守卫读的是两个任务模块的**源码文本**（AST），不进 `task_download`，
  不引入新依赖边。
