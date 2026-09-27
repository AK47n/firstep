# 04 — 参数表写加固：刷新路径不许把扫描刚写的新表盖回旧快照

**要做什么：** 学生应用一次参数值后表被刷新，同时参数扫描刚写进一张新表——
**新表不许被盖回旧快照**；写失败留意（刷新路径现在静默吞 `OSError`，残渣没人报）也不留垃圾文件。

**被谁阻塞：** 01（共享原语）。

**状态：** resolved（2026-09-27；读数、双轴评审处置、残留记账见文末）

## 现状（实测，带 file:line）

- 写实现：`src/contest_generator/params.py:283-292`——`tmp = path.with_name(path.name + ".tmp")`
  → `tmp.replace(path)`，**固定临时名、无锁、无 try/finally**。文件 = `.contest_params.json`（`:33`）。
- 两条写路径：
  1. `run_param_scan`（`:389`）里的 `write_params`（**`:412`**）：先 `llm.scan_params`（`404`，慢）
     再整份落盘，**全程不读旧表 = 整份盲写**（加锁无意义，本单只换写实现）。
  2. `_persist_applied_param`（`:468-492`）里的读-改-写：重读 `load_idea...`（`:482`）→
     纯刷新 `_refresh_param_after_apply`（`487`）→ 写 **`490`**；两者之间**无慢操作**，
     但写失败被 `except OSError: pass`（`491-492`）吞掉。
- 后果：`490` 写的是它 `482` 读到的快照 → 与 `412` 的整份盲写交叠时会把新表盖掉；
  两个 apply 交叠同理。
- 既有测试：`tests/test_params.py:224` 有一条**成功路径**残渣断言；
  无并发用例、无"写失败留残渣"用例。

## 验收标准

- [x] `params.py` 新增 `update_params(output_dir, merge: Callable[[ParamList], ParamList]) -> ParamList`；
      `write_params` 内部改走 `atomic_io.atomic_write_text`（字节格式逐字不动）。
      **补一条公开契约**（评审整改）：`merge` 返回**原对象** = 无事可做 → **不落盘**
      （"无文件 = 未识别过"这条既有契约照旧）。
- [x] `_persist_applied_param` 的落表改走 `update_params`（在**最新**盘上重放单参数刷新），
      **保留**「写盘失败不阻断主流程」的口径（吞 `OSError` 的语义不变，票里写明为什么保留）。
- [x] `run_param_scan` 的 `412` 保持整份替换（不读旧表 → 不上合并），只换写实现。
- [x] 域层用例（`tests/test_params.py`）：① 原子写无残渣；② 写失败无残渣 + 原异常；
      ③ 并发写不互抢；④ **交错不丢**：两条——两张表交叠（两个 apply 并发）与
      "扫描刚写的新表落在刷新那次读之后"（本单的主判据，判据取最终盘上内容）。
- [x] 端点级用例（`tests/test_params.py` 的既有参数端点附近）：apply 的落表与另一笔刷新并发，
      判据取最终落盘；撤锁注入下实测变红。
- [x] 反证探针 `.scratch/record-write-hardening/probe-04-red.py`（逐条声明 + 对账；**五段**）。
- [x] 读数落盘：定向 + 全量 `.txt`。

## 结论（读数、评审处置、账）

**形状。** `write_params` 的落盘改走 `atomic_io.atomic_write_text`（唯一临时名 + `finally` 清残渣）；
新增 `update_params`（`path_lock` + 重读 + 合并 + 落盘；`merge` 返回原对象 → **不落盘**）；
`_persist_applied_param` 的落表改走它——开头那次读只剩"判有没有表 / 表坏没坏"的作用，
**落表依据是最新盘上那份**。三条早退契约（`main.c` 读不出来 / 表损坏 / 无表）都还在，
`run_param_scan` 仍是整份盲写（不读旧表、不上合并），空表不落盘守卫未变。

**为什么保留「写盘失败不阻断主流程」**：走到这一步时编译验证已经成功、`main.c` 已经改好，
表回写只是让下次 `/read` 的 valid 重验不误判；为它把一次成功的 apply 报成失败，
学生会以为"没改成功"（东西其实改好了）。所以仍然吞掉——但现在**多吞一条 `TaskError`**
（表在这两次读之间变坏）：与"表损坏不覆盖坏文件"的早退同一口径，见下评审处置。

**不变量核对**：读侧中文错误文案逐字未动；JSON 字节格式**逐字节相同**——实测同一张表分别走
收走前的固定临时名实现与本单实现，落盘字节完全一致（`…]\r\n}\r\n`，**有**尾换行）；
`_refresh_param_after_apply` 仍是那个纯函数，合并在它之上重放。

**读数（本机实跑，全部 UTF-8 落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 定向 pytest | `python -m pytest tests/test_params.py -q` | **34 passed**（收走前 27 条） | `probe-04-tests.txt` |
| 反证（五段） | `python .scratch/record-write-hardening/probe-04-red.py` | **PASS**：A 撤临界区 → 两个 apply 交叠（域层 + 端点）两条红；B 重读挪到锁外 → 同上两条红；C 刷新退回旧形状 → "扫描新表不许被盖回快照" + 端点两条红；D 撤共享原语 → 写失败留残渣 + 并发抢临时名两条红；E 撤"无变化不写"短路 → "表被删不许凭空造空表"一条红。逐条声明与实得 `FAILED` 完全一致、每段复原 sha256 逐字节相同、复原后 34 passed | `probe-04-red.txt` |
| 全量 pytest | `python -m pytest -n auto -q` | **5631 passed + 11 skipped / 125.50s**（上一单基线 5624 + 11 → 本单 +7 条用例） | `probe-04-pytest.txt` |

**双轴评审（2026-09-27，`code-review` 跑在工作树 vs 固定点 `f4f105a6`）与处置。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Spec ①② / Standards ① | 票未翻牌、勾选框全空、无结论段；「为什么保留吞 `OSError`」只写在 docstring 里没进票；全量读数未落盘 | **属实**：本段补齐（翻 `resolved` + 勾选 + 读数表 + 保留理由） |
| Spec (b) / Standards ③ | `_persist_applied_param` 丢掉了旧的 `if refreshed is not param_list` 短路 → 合并无改动时也会重写文件 | **属实，已修**：短路**搬进** `update_params`（`merge` 返回原对象 → 不落盘），`_refresh_param_after_apply` 的 docstring 同步对齐（"调用方按 `is` 判要不要落盘"） |
| Spec (c)① | **空表窄洞**（评审实测复现）：预检时表在、锁内重读之前文件消失 → 会落一张 `"params": []`，与"无表 = 未识别过、不凭空造空表"相悖 | **属实，已修**：靠上面的短路关掉；新增判据 `test_persist_applied_param_does_not_create_a_table_that_vanished`（探针 E 段声明它） |
| Spec (c)② / Standards ② | 同一窗口里表变**损坏** → `TaskError` 穿出主流程（路由补 error 终态，而 `main.c` 其实已改好） | **属实，已修**：落表处补 `except TaskError`（与早退同口径，不覆盖坏文件、不阻断主流程） |
| Spec (c)③ / Standards ⑥ | 并发判据缺"已发出"握手，撤锁那一格可能假绿（判据抢跑） | **属实，已修**：域层与端点两处都加 `*_started.wait(timeout=30)` 握手（照 `tests/test_hwcheck.py:3399` 先例） |
| Standards ④ | `update_params` docstring 里「扫描…只会被别人的临界区挡在极短一瞬」不实——扫描不取锁、没人挡它 | **属实，已修**：改成如实说明（扫描的盲写仍可能落进临界区），并把残留指向票尾「账」第 1 条与工单 06 |
| Standards ⑤（判断项） | `_run_in_thread` 在本批第三份逐字复制，且引用写成"照 `tests/test_hwcheck_triage.py` 先例"（那份文件并无此 helper） | **部分采纳**：本单把引用改准（指向 `:625-645` 那段并发先例的形状）；**三份收成一处**记进工单 06（动 02/03 的判据文件会让它们已提交的读数脱钩，交给 06 的汇总轮一次做） |

**账（留给后面的人 / 工单 06）：**

1. **扫描的整份盲写 × 刷新的临界区——未记账的残留（本单没封死）。** 本单把刷新的
   read→merge→write 关进锁，但扫描那条盲写**不取锁**（spec 定的"只换写实现、不上合并"）：
   它若正好落在刷新"锁内读完 → 写之前"那几微秒里，仍会被刷新那份记录盖掉——评审按此时序
   **实测复现**（最终盘只剩 `THRESHOLD=900`，扫描新写的那条整条丢）。spec「范围外」没列它，
   所以是**未记账**而非已承认。封死办法是给扫描的盲写也套同一把 `path_lock`（它不读旧表，
   加锁只是多等临界区那几微秒），但这与本票"只换写实现"的边界冲突 → **留给工单 06 定夺**
   （06 的工单里已补上这条）。本单的端点级判据里，并发那笔走的是**有锁的** `update_params`
   （"另一个 apply"那一族），**不是**扫描的盲写——如实记账，不假装覆盖。
2. 域层那条"两个 apply 交叠"的注入点是**首个读**（第一次 `load_params_file` 时把新表写进盘），
   它钉的是"落表依据是最新盘上那份、不是开头读到的快照"；端点那条钉的是"两笔写串行"。
   两条各钉一半，交叉处（扫描盲写撞临界区）见上一条。
3. `_run_in_thread` 现在有三份同形（`test_drafts.py` / `test_idea_chat.py` / `test_params.py`）
   → 收成一处这件事记在工单 06 的收口范围里。

## 备注

- 空表不落盘的既有契约（`params.py:409-412` 注释：无文件 = 未识别过）**不许变**。
- `_refresh_param_after_apply` 是纯函数，合并闭包里复用它，别在合并里重写逻辑。
