# 06 — 收口：结构守卫 + 反证汇总 + 台账翻牌

**要做什么：** 这一批做完后，让"全仓只有一个原子写实现"这件事**被机器盯住**，
把四条反证读数与全量闸门读数落盘，并把 `backlog.md` §24 翻牌——**连同"还有哪些站点没修"一起写清楚**。

**被谁阻塞：** 02、03、04、05。

**状态：** resolved（2026-09-27；含补做的双轴回顾评审处置，见文末）

## 验收标准

- [x] **结构守卫**（新用例，家 = `tests/test_atomic_io.py`）：
      扫 `src/contest_generator/**.py` 里的原子写站点，要求每一处要么是共享原语自己、
      要么在**例外清单**里且**逐条带中文理由**（形状照
      `tests/test_library_invariants.py::SINGLE_PLATFORM_REASONS` 的先例）。
      **判据面（回顾评审后写清楚，比原文窄）**：站点 = 「造临时路径」那一行
      （赋值行里带 `tmp` 的字面量）＋「换入」那一行（`os.replace(`）；
      `X.replace(` / `X.rename(` 的任意写法**不单独抓**（只抓半边会淹在 `str.replace` 里），
      纯常量赋值（`TMP_SUFFIX = ".tmp"`）也不算站点。已知盲区（写在用例 docstring 里）：
      棘轮只比"每文件站点数"，同文件里坏站点换好站点数量不变时看不出来。
      例外清单（**6 条**，比工单原文多一条）：`codeview.py`(4) / `recent_jobs.py`(2) /
      `hwcheck_triage.py`(2，**工单 07 落地后已删**——棘轮当场点名"清单发霉") /
      `materials_apply.py`(2) / `master_store.py`(3，全是**目录**换入) /
      **`my_devices.py`(1，守卫跑出来补的第 6 条**：自建件落盘是目录级 staging + rename)。
      正向对照：塞一个手搓固定临时名的反例文件 → 必红；清单里的站点没了 → 报"已经没了"。
- [x] **反证汇总**：**五张单**（01–05）的 `probe-0X-red.py` 读数汇总成一份
      `.scratch/record-write-hardening/probe-06-red-summary.txt`，每条**逐条声明 + 与实得 `FAILED` 对账**
      （多出来的红如实打印，不据此判 PASS）；每条都要有"复原后回绿"的读数。
- [x] **台账翻牌**：`backlog.md` §24 标 ✅ 已收口，并**如实列出未修的站点**
      （`materials_apply._extract_zip`、`entry_store.write_json` 的裸写、跨进程并发、强杀残留清扫），
      附一句"下次复核按直接读盘核对的模式，不信本节旧标记"——§23 那个坑（修完没人回改标记）不许重演。
- [x] **05 的前置小账**（前面几张单的评审留下、逐条要在这里结清）：
      1. `_run_in_thread` 在本批复制了**四份**（`test_drafts.py` / `test_idea_chat.py` /
         `test_params.py` / `test_master_store.py`）——收成一处（`tests/` 里的小工具模块，
         形状照 `tests/test_impact.py::_sse_events` 被别的用例文件 import 的先例）；
      2. `atomic_io.py` docstring 里「本批的调用方都在各域的 `update_*` 里持锁」**已过期**
         （05 的 `_write_meta` 是整份重写、直接持锁）——对齐；
         ⚠ 动了 `atomic_io.py` 就会让 01–04 已提交读数里绑的 sha256 变旧 →
         **汇总轮要重跑 01–04 的探针读数**（本票第 2 条本来就要重跑一遍汇总）；
      3. 工单 04「账」第 1 条：**扫描的整份盲写 × 刷新的临界区**——扫描不取锁，落在
         刷新"锁内读完 → 写之前"那几微秒里仍会被盖掉（评审实测复现）。要不要给扫描的
         盲写也套同一把 `path_lock`（一行，且它不读旧表）→ 本票定夺并落账；
      4. 工单 04「账」第 2 条：spec:55「三个记录文件有尾换行」与实际不符
         （两份聊天记录**没有**尾换行）——按实际字节核不变量，别按那句话核；
      5. 工单 05「账」第 1 条：`import_master` 的**目录换入**（`master_store.py:519`）
         在 meta 锁之外，它与 `delete_master` 的 `delete_entry` 之间留着一条窄缝
         （评审实测复现"有 meta、没目录"）。要不要把锁提到目录换入之前
         （并把 `delete_entry` 也包进来）→ 本票定夺并落账。
- [x] **读数落盘**：全量 `python -m pytest -n auto -q` 一份 `.txt`；
      并写明"落点不在 `static/` 或 `tests/js/`，故未跑前端 / 浏览器门禁"（或如实说明为何跑了）。
- [x] **边界记账**（写进 spec 或本票结论段）：跨进程并发不在射程（单进程应用）、
      锁表只增不减、强杀残留不扫——三条都要有落脚处，别只留在会话里。
- [x] `docs/agents/local-environment.md`：若本批改变了"这台机器 + 此刻"的任何事实
      （端口 / 沙箱 / 发版落差），当场回改；没有则不动（别为凑数改文件）。

## 结论（做了什么、读数、边界记账）

**一、结构守卫（新用例，家 = `tests/test_atomic_io.py`）。**
`test_only_one_atomic_write_implementation_in_src`：扫 `src/contest_generator/**.py` 的**两种站点**——
造临时路径那一行（`… + ".tmp"` / `mkstemp(suffix=".tmp")`）与换入那一行（`os.replace(`）——
要求每个文件要么就是共享原语自己（`atomic_io.py`），要么在 `ATOMIC_WRITE_EXCEPTIONS` 里
**逐条带中文理由**，且**站点数对得上**（棘轮：新增/删除站点都要复核理由；清单发霉也报）。
清单六条：`codeview.py`(4) / `recent_jobs.py`(2) / `hwcheck_triage.py`(2，工单 07 迁走后这条要删) /
`materials_apply.py`(2) / `master_store.py`(3，全是**目录**换入) /
**`my_devices.py`(1，守卫跑出来补的第 6 条**：自建件落盘是目录级 staging + rename）。
正向对照 `test_atomic_write_guard_catches_a_new_hand_rolled_site`：临时塞一个手搓固定临时名的
反例文件 → 必红（反向：清单里的站点没了 → 报"已经没了"）。

**二、反证汇总（`probe-06-red-summary.txt`）。** 五张单的探针**在当前字节上重跑一遍**
（代码收口后 `atomic_io.py`、各判据文件都动过，旧读数已脱钩 → 五份读数全部重生成、重新绑字节），
汇总里逐段保留「声明必须红 / 实得 FAILED / 复原 sha256 逐字节相同」，末尾判定表 **5/5 OK**。
汇总脚本只搬运各探针自己的输出与结论，不替它们判 PASS。

**三、台账翻牌。** `backlog.md` §24 的「另三处同构的固定临时名 + 无锁记录写仍未修」已改成
✅ 已收口，并**如实列出这一批明确没修的**：`materials_apply._extract_zip` 的固定 `.update-tmp`、
`entry_store.write_json` 的裸写、跨进程并发、强杀残留清扫、母版"目录换入 × 删 meta"的窄缝；
末尾写明**下次复核按"直接读盘核对"的模式，不信本节旧标记**（§23 那个坑）。

**四、边界记账（三条，都有落脚处，不只留在会话里）。**

| 边界 | 落脚处 |
|---|---|
| **跨进程并发不在射程**（单进程 `uvicorn.run`，锁是进程内的） | `atomic_io.py` docstring「边界」段；spec「范围外」；`backlog.md` §24 |
| **锁表只增不减**（每个见过的路径一把锁；弱引用会把"锁被回收"变成真竞态） | `atomic_io.py` 里 `_PATH_LOCKS` 上方那段记账注释（照 `hwcheck_triage.py:389-391`） |
| **强杀残留不扫**（只清本进程本次写失败留下的临时文件） | `atomic_io.py` docstring「边界」段；spec「范围外」；`backlog.md` §24 |

**五、前置小账五条（前面几张单的评审留下的）——逐条结清。**

1. `_run_in_thread` 四份复制 → 收成 `tests/concurrency.py::run_in_thread`（迁移脚本
   `.scratch/record-write-hardening/apply-06-helper.py`；四个判据文件 + `test_webapp.py`
   的端点用例改成 import 它）。
2. `atomic_io.py` docstring 里「调用方都在各域 `update_*` 里持锁」→ 已对齐（含 05 的
   `_write_meta` 那条整份重写路径），并把尾换行那句按**实测**写成"两份聊天记录与母版 meta 没有、
   其余三个记录文件有"。
3. **扫描的整份盲写 × 刷新的临界区** → **关掉了"新表被旧快照盖掉"那条**：`run_param_scan`
   的落盘现在也取同一把 `path_lock(params_path(...))`（它不读旧表，加锁只让它多等临界区那几微秒）。
   新增判据 `test_param_scan_write_does_not_land_inside_a_refresh_critical_section`
   （探针 04 的 F 段声明它；A 段撤临界区时它也会红——如实并进 A 段声明）。spec 表格同步更正。
   ⚠ **没改的是扫描自己的语义**：晚到的扫描仍会整份覆盖（吞掉学生刚应用的那个值）——
   属产品决策，已记进 spec「范围外」。
4. spec 里「三个记录文件有尾换行」→ 按实际字节更正（`.contest_ideas.json` /
   `.contest_params.json` / `.hwcheck_record.json` 有；两份聊天记录与母版 meta **没有**）。
5. 母版"目录换入 × 删 meta"的窄缝 → **明确承认为已接受的残留**（写进 spec「范围外」：
   窗口毫秒级、后果只是库目录里一份没人读的 json；要闭得把锁提到目录换入之前并权衡
   `rmtree(backup_dir)` 期间持锁的代价。真要改另开单）。

**六、`docs/agents/local-environment.md`**：本批把 `main` 与线上 v1.3.1 的落差从"归零"变回
"多一批未发布改动（**用户可见影响：无**）"——当场回改了 §0（发版落差那条正是这份文件要记的
"这台机器 + 此刻"事实；端口 / 沙箱没动）。

**读数（本机实跑，全部 UTF-8 落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 结构守卫 + 原语定向 | `python -m pytest tests/test_atomic_io.py -q` | **9 passed**（含两条新守卫） | 见下"全批次定向" |
| 全批次定向 | `python -m pytest tests/test_atomic_io.py tests/test_drafts.py tests/test_idea_chat.py tests/test_params.py tests/test_master_store.py -q` | **134 passed** | `probe-06-tests.txt` |
| **反证汇总** | `python .scratch/record-write-hardening/probe-06-red-summary.py` | **5/5 OK**：五张单的探针在当前字节上重跑，逐段声明与实得 `FAILED` 全对上、复原 sha256 逐字节相同、复原后回绿 | `probe-06-red-summary.txt` |
| 全量 pytest | `python -m pytest -n auto -q` | **5639 passed + 11 skipped / 113.45s**（05 基线 5636 + 11 → 本单 +3 条用例） | `probe-06-pytest.txt` |

**闸门范围**：本批落点全在 `src/contest_generator/**` 与 `tests/**`（后端），
**不在 `static/` 或 `tests/js/`**，故未跑前端门禁与浏览器门禁（照 spec「测试决策」的闸门口径）；
`tools/prepush.py --changed <文件>` 选的关联子集也已跑过。

## 备注

- 这一批**不改用户可见文案**，故预期 CHANGELOG 只有内部加固类条目（提交信息照实写中文即可）。
- 收口时顺手核过：四处的错误文案与 JSON 字节格式没被顺手改掉
  （spec「不变量」段三条逐条核；尾换行按**实际字节**核，见前面第 5 条小账）。
- hwcheck_triage 的私有副本由**工单 07** 迁走——本票的结构守卫清单里那条理由写到时同步删掉。

## 双轴回顾评审（2026-09-27 补做，跑在提交 `fd8d2645` 上）与处置

> 收口单当时漏跑了评审（本批 02–05 都跑了），回头补上；下面逐条处置。

| 轴 | 发现 | 处置 |
|---|---|---|
| Standards 硬 | `params.py` 的 `update_params` docstring 仍写"扫描…**不取锁**……留给工单 06 定夺"，而同文件 `run_param_scan` 已经加锁——同文件两段自相矛盾 | **属实，已修**：那段改成"它也取同一把按路径的锁（工单 06 收口）"，并指向 spec「范围外」的语义残留 |
| Spec (a) | 验收原文写"`os.replace(` / `Path.replace(` 形态"，实现只抓了"造临时名 + `os.replace(`"，却打了 `[x]` 没说判据面变小 | **属实，已修**：验收条款改写清**判据面**与**已知盲区**；用例 docstring 同样写清（`X.replace` / `X.rename` 不单独抓的理由一并写上） |
| Spec (a) | 验收原文写"**四张单**的探针汇总"，实际汇总了五张（01–05） | **属实，已修**：改成五张 |
| Spec (a) | `§24` 的 ✅ 与守卫一起暗示"全仓只有一个原子写实现"，而 `hwcheck_triage` 此刻仍是第二份（07 未落地），且它只写进了白名单理由、**没进「未修清单」** | **属实，已修**：07 落地后这条自动消失（清单里那条已删）；`§24` 的 ✅ 现在名副其实 |
| Spec (a) | `local-environment.md` §0 写"整批（工单 01–07）在 main 上"，而 07 当时一行没上 | **属实，已修**：那句话随 **07 的提交**一起落地（本票提交时 07 还没提，所以它没算在 06 里） |
| Standards 判断 | 守卫**名实不符**（判据面比名字窄）；`TMP_SUFFIX = ".tmp"` 这类纯常量会误报；棘轮只比数量、坏站点换好站点看不出来 | **部分采纳**：① 判据面写清（见上）；② 纯常量赋值已排除（新增 `_TMP_CONSTANT`，用例里有正向断言）；③ "同文件换站点"这条盲区**如实写进用例 docstring**，不改设计（改成比对位置会更脆） |
| Spec (c) | 汇总脚本的判定只看"退出码 + 结论行 + 无 `[x]`"，**不核段数**——探针被删掉两段、其余仍 PASS 也会判 [OK]；标题把退出码写成"readings.py 退出码"；不记仓库修订 | **属实，已修**：脚本改为逐单核对**段数**（3/3/5/6/3）、标题改"探针退出码"、头部打印 `HEAD` 与工作树脏否；重跑生成新读数 |
| Spec (c) | 扫描加锁只关掉一半：晚到的扫描仍会**整份吞掉**学生刚应用的值；新判据只断言盘上名字，等于把"扫描该赢"钉成口径 | **属实，已记账**：spec「范围外」新增"扫描的整份覆盖语义"一条（要改得先回答"扫描晚到时按什么合并"，属产品决策）；本票结论第 5 条的措辞从"关掉"改成"关掉了'新表被旧快照盖掉'那条" |
