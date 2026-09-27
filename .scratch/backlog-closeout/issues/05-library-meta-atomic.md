# 05 — 库更新路径的元数据写盘不是原子的（事务只盖住"新建"那半边）

**要做什么：** 三个库的**更新**动作把元数据 JSON 直接写进**活着的条目目录**——进程被杀
（不是抛异常）会留下**截断的元数据**，那一条目从此读不出来；把这几处收进共享原语
（`atomic_io.atomic_write_text`），既有的"异常期恢复"逻辑保留不动。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-09-27；读数、双轴评审处置、账见文末）

## 现状（实读盘取证，工单 `backlog-closeout/04` 的产物）

`entry_store.write_json` 的 7 个调用点里，**新建**那半边在事务里，**更新**那半边不在：

| 调用点 | 是否在 `entry_transaction` 里 | 备注 |
|---|---|---|
| `library.py:454`（`add_module`） | ✅ 在（`:437`） | 新建模块 |
| `reference_library.py:985`（`add_reference`） | ✅ 在（`:983`） | 新建参考 |
| `reference_library.py:1148`（`archive_reference`） | ✅ 在（`:1144`） | 归档入库 |
| `topic_library.py:229`（`confirm_topics`） | ✅ 在（`:223`） | 一次建多条 |
| `my_devices.py:306` | ✅ 靠目录级 staging + rename | 自建件 |
| **`library.py:712`（`_write_manifest`）** | ❌ **不在** | 调用链：`save_manifest`（`:335`）← `update_platform_identity:367` / `update_module_description:484` / `add_platform_files:545` / `remove_platform_files:586` |
| **`reference_library.py:1085`（`update_reference`）** | ❌ **不在** | 活条目目录上直接写 `reference.json` |
| **`topic_library.py:502`（`update_topic`）** | ❌ **不在** | 活条目目录上直接写 `manifest.json` |

**后果（这条才是要点）**：这三处都有**异常期恢复**（`except` 里删新文件 / 写回旧文本），
但 `write_text` 被**强杀/断电**打断时 `except` 根本不会跑——盘上留下的是**半截 JSON**，
`read_json` 抛 `StoreParseError`，该条目在界面上就是一个打不开的坏条目。
这正是 `record-write-hardening` 那一批在治的同一类病（固定临时名/裸写 → 原子写），
只是当时按"`entry_store` 靠目录级事务兜底"一句放过了——**那句话只对新建立成立**。

## 验收标准

- [x] 三处改成 `atomic_io.atomic_write_text`（唯一临时名 + 换入 + 清残渣），
      **既有异常期恢复逻辑保留**（原子写解决"被杀"，恢复逻辑解决"业务失败"——两件事都要）。
- [x] 结构守卫（`tests/test_atomic_io.py::ATOMIC_WRITE_EXCEPTIONS`）不动它（这几处不是"手搓临时名"，
      是**裸写**——守卫现在扫的是前者；若顺手把"裸 `write_text` 到条目目录"也纳入扫描面，
      得先把这份清单钉住，别让它变成永远红的噪音）。
- [x] 判据（每个库各一条，形状照 `tests/test_materials_apply.py` 的 `test_apply_manifest_write_is_atomic`）：
      注入写失败（目标位置占成目录 / patch 原语）→ **零杂散文件**且**旧元数据不动**；
      再加一条"强杀"模拟（写临时文件后直接抛，不走 `except` 恢复）→ 条目仍可读。
- [x] 反证探针：撤掉原子写 → 对应判据红（逐条声明 + 对账 + 复原 sha256 逐字节）。
- [x] 读数落盘：定向（三库）+ 全量 `python -m pytest -n auto -q`。

## 结论（形状、读数、评审处置、账）

**形状。** `entry_store` 新增 `write_json_atomic(entry_dir, filename, data)`（唯一临时名 →
`os.replace` → `finally` 清残渣，走 `atomic_io.atomic_write_text`——实现只有那一份）；
序列化与 `write_json` 同一份（提成 `_json_text`，落盘字节逐字不变）。三处**更新**入口改走它：
`library._write_manifest`（`save_manifest` 的四个更新调用方都经这里）/ `reference_library.update_reference` /
`topic_library.update_topic`；**新建**那半边（`entry_transaction` 里的 `write_json`，剩 5 个调用点）
原样不动——事务清目录兜着。三处既有异常期恢复逻辑**一字未动**（原子写解决"被杀"、
恢复块解决"业务失败"，两件事都留着）。

**为什么加一只新的，而不是把 `write_json` 本体改成原子**：新建那半边写的是刚 `mkdir` 的空目录，
多一次 rename 没收益；04 的账正是把两半边的边界写清楚的（新建靠事务、更新是裸写），
批 spec:98 也把"`entry_store.write_json` 的改"划在本批之外。两只只差"落的这一步"，
名字里的 `_atomic` 就是那条差别；锁的边界另写进了它的 docstring。

**读数（本机实跑，全部 UTF-8 落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 定向 pytest | `python -m pytest tests/test_library.py tests/test_reference_library.py tests/test_topic_library.py tests/test_entry_store.py tests/test_autocommit.py tests/test_atomic_io.py -q` | **473 passed** | `probe-05-tests.txt` |
| 反证（五段） | `python .scratch/backlog-closeout/probe-05-red.py` | **PASS**：A 撤原子入口（`entry_store` 退回裸写）→ **六条全红**；B/C/D 三库各自那处退回裸写 → 各自两条红（逐处归因）；E 撤共享原语的清残渣 → 三条"零杂散"红；逐条声明与实得 `FAILED` 全等、每段复原 sha256 逐字节、复原后 6 passed | `probe-05-red.txt` |
| mypy | `python -m mypy src/contest_generator/{entry_store,library,reference_library,topic_library}.py` | 本单四个文件**零错**；同一命令随 import 闭包带出的 9 条既有错全在没碰过的文件（`pin_bindings` 6 / `syscfg_prune` 1 / `skeleton` 1 / `hwcheck_triage` 1） | `probe-05-mypy.txt` |
| 全量 pytest | `python -m pytest -n auto -q` | **5656 passed + 11 skipped**（上一单 03 的基线 5650 + 11 → 本单 +6 条判据） | `probe-05-pytest.txt` |

**双轴评审（2026-09-27，`code-review` 跑在工作树 vs 固定点 `52f50333`）与处置。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Standards 硬① / Spec (a) | 全量读数没落盘（票里要"定向 + 全量"） | **属实**：评审看的时候全量还在后台跑（现在已落盘，见上表最后一行） |
| Standards 硬② / Spec (c) | 三处调用点是"先读后写"却**不持 `path_lock`**，与 `atomic_io` docstring 的契约（"调用方自己持锁"；同一目标并发 `os.replace` 会 `WinError 5`）不符 | **记账 + 把边界写进原语 docstring**：本单射程只到"落的这一步是原子的"；串行化要盖住 6 个 `update_*` 的**整个**读-改-写。**不能**往 `write_json_atomic` 里塞锁——将来调用方在外面按同一路径持锁时会自死锁（`path_lock` 不可重入），那段话已写进它的 docstring。残留的失败面是"后写的赢 / 报错"，不是"条目变坏"；记进票尾「账」与 `backlog.md` §26 |
| Spec (b) | 越界：新增公开 API `entry_store.write_json_atomic` + 把序列化提成 `_json_text`，而批 spec:98 写着"`entry_store.write_json` 的**改**：本次只核实与记账" | **属实但有据，记账**：spec:98 划的是 `04` 那单的射程（它按验收标准"不改代码"）；`05` 是它核出来的**修单**，验收标准第 1 条明写"三处改成 `atomic_io.atomic_write_text`"。正因为有那半句，本单选的是**加一只新的**而不是改 `write_json` 本体——`write_json` 的行为与落盘字节零变化（见上「为什么」） |
| Spec (b) | `tests/test_autocommit.py` 的 `_WRITE_MARKERS` 补 `write_json_atomic(` 不在票的文件清单里 | **属实、保留**：那是守卫自身的规矩（"read 类函数含写原语即红"），写原语集合必须跟代码走；不补就等于让"read 函数偷写元数据"漏网。记账在此 |
| Standards 判断③ | `write_json` / `write_json_atomic` 的名字藏着"哪只给哪种目录用"的约束（Mysterious Name），建议改名（如 `write_json_in_new_dir`）或加结构守卫钉住调用点 | **部分采纳，不按建议改**：约束已写进两只的 docstring（本单又补了锁边界那段）。改名要动 5 个调用点 + 3 处测试注入点（`reference_library` 的事务路径测试也挂在 `write_json` 上）与上游文案，换来的只是措辞。结构守卫那条：票的验收标准 2 已明确"不动它"；而且机器判不了"这个目录是不是刚建的"——只能量文本形状，量出来还得给 `my_devices` 的暂存-改名调用点开白名单，正是票里警告的"永远红的噪音"。**记账不补** |
| Standards 判断④ | Duplicated Code：`tests/_meta_write_failure.py::break_write` 的"先写半截再抛"与 `tests/test_atomic_io.py` 那条同名手法重复；两处旧注入点仍是内联 lambda | **记账不补**：前者是**原语自己的用例** vs **三库域层用例**，共享要跨族耦合一个 helper、收益 4 行；两处内联 lambda 是**既有**用例（本单只把注入符号从 `write_json` 改挂 `write_json_atomic`，语义未动）——最小 delta 更好 review |
| Spec (c) | 强杀那条判据测不到残渣（`Killed` 是 `BaseException`，`finally` 照跑、临时文件照清） | **属实、如实记账**：helper 的 docstring 已写明"本模拟比真强杀宽松"；判据只取"元数据没被截断、条目仍读得出来"——真 SIGKILL 会毁掉的正是这个。残渣清扫属批 spec 明划的范围外（"强杀残留清扫"） |

**账（留给后面的人）：**

1. **三库更新路径的"读-改-写"没有串行化**（本单只做了原子落盘）：两个写者同时改**同一条目**时是
   "后写的赢"，还可能撞上 Windows 对同一目标并发 `os.replace` 的 `WinError 5`。要做对，得给 6 个
   `update_*`（`library` 四个 + `update_reference` + `update_topic`）在**外层**持
   `path_lock(entry_dir / <元数据名>)` 包住整个读-改-写；**不能**塞进 `write_json_atomic`（自死锁）。
   已记 `backlog.md` §26「顺带量到、不动」。
2. **条目目录里的内容文件仍是裸写**（`reference_library` 的 `add_files` / `_write_files`、
   `topic_library` 的题面 `.md`）——票面备注就划在这里；要不要一起原子化是下一张单的判断
   （它们更大、更慢，成本不同）。
3. **强杀模拟代替不了真 SIGKILL**：`Killed(BaseException)` 走的是"`except` 恢复块不跑"这条路径，
   `finally` 仍会跑；判据因此**不查残渣**，只查"旧元数据逐字节不动 + 条目仍可读"。

## 备注

- 射程**只到"元数据 JSON 写盘"**：条目目录里的**内容文件**（`reference_library` 的
  `add_files`/`_write_files`、`topic_library` 的题面 .md）仍是裸写 + 异常期恢复——
  要不要一起原子化，是下一张单的判断（它们更大、更慢，成本不同）。
- 这条与 `backlog-closeout/04` 是一对：**04 只说"核实在案"，05 才是修**。
