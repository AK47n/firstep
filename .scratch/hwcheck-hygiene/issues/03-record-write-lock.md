# 03 — 检测记录的写：唯一临时名 + 原子替换 + 短临界区（并发两处入口不丢更新）

**要做什么：** 两个页面同时勾选 / 回填时，检测记录**不许丢更新、不许互相覆盖临时文件**——
学生在检测页勾的上板清单，不会因为同时在排障面板提交了一次回填就被写回去。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**来源**：评审 P2-9（Y5）。**实测更正**：评审建议"纳入 `_generation_guard`"——那条守卫是
"每键互斥 + 冲突 409"（`webapp.py:1607-1622`），用在记录写上会让学生**生成期间连勾选都存不了**；
全仓也没有"记录写加锁"的先例。正确形状是**短临界区**，见下。

## 现状（实测）

- 清单落盘：`src/contest_generator/webapp.py:3255-3267`，读-改-写在 `:3264-3266`
  （`read_hwcheck_record` → `record_with_checked` → `write_hwcheck_record`），无锁。
- 排障落盘：`webapp.py:3225-3244`，读在 `:3225`、写在 `:3244`，**中间 3228-3242 是整段 LLM 调用**
  ——窗口跨越秒级时延，是最容易丢更新的那条。
- 写实现：`src/contest_generator/hwcheck_triage.py:776-785`，**固定临时名**
  （`tmp = path.with_name(HWCHECK_RECORD_FILENAME + ".tmp")` → `tmp.replace(path)`）：
  两个写者会抢同一个 `.tmp`，且"坏写留半成品"的原子性承诺在并发下不成立。
- 第三条读路径 `webapp.py:3166`（只读展示）不参与读-改-写，**不改**。
- 同构的另三处（`idea_chat.py:167-169`、`drafts.py:115-118`、`params.py:284-286`）同样"固定 tmp + 无锁"——
  **本单不改**，只在票里记账（改它们要各自的行为判据与回滚面，见 spec「范围外」）。
- 仓内唯一带 pid 后缀的原子写先例：`codeview.py:362` / `:532`（`f".tmp-{os.getpid()}"`）。

## 验收标准

- [x] 临时名唯一（pid + 单调计数/uuid；照 `codeview.py` 先例或更好），写完 `replace` 原子替换；
      异常路径不留下 `.tmp` 残留（坏写不许留半成品）。
- [x] 读-改-写整段进**短临界区**（按记录路径的一把进程内锁；排障那条把 LLM 调用移到临界区**之外**，
      临界区内只做"**重读 → 合并**（勾选态 / 现象 / 建议各自字段） → 写"）——
      这样"生成中点勾选"与"排障回填"可以并存，谁也不 409。
- [x] 合并语义要**按字段**：LLM 调用期间别人改过的 `checked_ids` 不许被这次回填的旧快照覆盖
      （这条是丢更新最真实的形态，必须有专门用例）。
- [x] pytest 用例（进程内真并发，照仓内既有并发用例先例）：
      ① 两线程各写不同字段 → 两笔都在；② 模拟"LLM 调用窗口内别人写了 checked_ids" →
      回填后 checked_ids 仍是别人的新值 + 现象/建议是本笔的；③ 同一路径并发写 → 不出现
      `.tmp` 抢用/半成品（断言目录里除记录文件外无残留）。
- [x] **反证**：把临时名改回固定名（或把临界区撤掉）→ 相应用例红；复原后 sha256 逐字节相同
      （`.scratch/hwcheck-hygiene/probe-03-red.py` / `probe-03-red.txt`）。
- [x] 读数：`python -m pytest -n auto -q`（全套）与 `-k "hwcheck or triage or record"` 两个读数都落盘。
- [x] 票里记一句"另三处同构写未修"的账（位置与理由），别让下一个人以为已经全修了。

## 结论（读数与账）

**形状。** 三点都在域层（`hwcheck_triage.py`），端点只负责"什么时候调"：

| 那一半 | 落点 | 说明 |
|---|---|---|
| 唯一临时名 | `write_hwcheck_record` | `…json.tmp-<pid>-<进程内计数>` → `os.replace`；`finally` 清残渣（成功路径 tmp 已被换走，失败路径才清） |
| 短临界区 | `_record_lock` + `update_hwcheck_record` | 一把**按记录路径**的进程内锁（键按 `normcase(abspath())` 归一，免得盘符大小写 / 斜杠写法各发一把）；临界区里只做"重读 → 合并 → 写" |
| 按字段合并 | `record_with_triage` | 现象 / 建议是本笔的；勾选**只有**在"模型思考那几秒里没人动过记录"时才照写（`base` = 调模型前读到的那份，临界区里重读到的与它相等 = 没人动过） |

排障端点因此变成：**调用前读一次 `base`**（既是合并基准，也让"记录文件坏"当场 400、不白花一次
模型调用）→ **LLM 调用在临界区之外** → `update_hwcheck_record(...)` 里合并落盘。
清单端点同样走 `update_hwcheck_record`。**没有**照 `_generation_guard`（那是"每键互斥 + 冲突 409"，
用在记录写上会让学生生成期间连勾选都存不了）。带 pid + 计数的临时名比仓内先例
（`codeview.py` 只带 pid）更进一步：同进程内两个写者也必须不同名。

**读数（本机实跑，落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 全套 pytest | `python -m pytest -n auto -q` | **5587 passed + 11 skipped**（≈212s；上一批收尾基线 5581 + 11） | `probe-03-pytest-full.txt` |
| 定向 pytest | `python -m pytest -n auto -q -k "hwcheck or triage or record"` | **657 passed + 10 skipped**（≈85s） | `probe-03-pytest-hwcheck.txt` |
| 反证 | `python .scratch/hwcheck-hygiene/probe-03-red.py` | A（固定临时名）2 条红 / B（撤临界区）2 条红；两次复原 sha256 逐字节相同、回绿 | `probe-03-red.txt` |

反证探针**逐条点名**声明哪些用例必须红，并把实得 `FAILED` 集合与声明对账（多出来的红如实打印、
不据此判 PASS）——第一版只判"有没有红"，被双轴评审抓到"账实不符"（B 段实得 1 failed 1 passed
却打了 ✓），已改成现在的形状。

**另三处同构写未修（本单只记账，不动）**——都是"固定 `.tmp` + 无锁"，改它们要各自的行为判据与
回滚面（spec「范围外」）：

| 位置 | 形态 |
|---|---|
| `src/contest_generator/idea_chat.py:167-169` | `path.with_name(filename + ".tmp")` + `replace`，无锁 |
| `src/contest_generator/drafts.py:115-118` | 同上（注释里自述"照 idea_chat.py"） |
| `src/contest_generator/params.py:284-286` | 同上 |
| `src/contest_generator/master_store.py:637-645` | **评审补记的第四处**：`f".{platform}.json.tmp"` + `os.replace`，无锁、**也没有 finally 清残渣**（原票只点了三处，这里按实测补上） |

**双轴评审（Standards / Spec，2026-09-26）与处置。**

| 评审发现 | 处置 |
|---|---|
| 硬：工单状态没改 `claimed` 就开工 | 属实（本单漏了这一步）——已在收口时置 `resolved`；**下一单起按 workflow 先 claim** |
| 硬：反证读数与结论不符（B 段"1 failed, 1 passed"仍报 ✓） | 探针改成**逐条声明 + 对账**，多余的红如实打印（见上） |
| 判：既有守卫 `glob("*.tmp")` 匹配不到新临时名 = 断言空转 | 改成"目录里除记录文件外一个文件都没有"（`iterdir`），并把这条判据的说明写进用例 docstring |
| 判：端点那条用例撤锁照样绿 = 测不出锁 | 新增一条**锁敏感**的端点用例 `test_two_endpoints_serialise_their_record_writes`（判据取最终落盘，不取响应体）；撤锁注入下实测变红 |
| 判：并发临时名用例把补丁打在**全局** `os.replace` 上，跨用例偶发 | 补丁收敛到"目标模块看到的 `os`"（`SimpleNamespace`），并如实记进用例 docstring |
| 判：`_RECORD_LOCKS` 只增不减 | 保留（本地工具规模有限；弱引用反而会把"锁被回收"变成真竞态）——已在代码里记账 |
| 判：`record == base` 用整记录相等可能因 `_stamped` 误判 | **复核不成立**：`read_hwcheck_record` 读的是盘上那份，首次写的戳已在盘上；"无文件"两处都是未盖戳的空记录，仍相等。行为正确，不改 |
| 判：现象 / 建议无条件覆盖，同窗口另一笔回填的现象会被盖 | 属实（last-write-wins 的既有语义，本单只按字段挡勾选）——记在这里，属设计余量 |
| Spec：前端注释未被要求就动 | 那句注释原文说"服务端据此落盘"，本单改了落盘口径，不改就是留着过期的话；已同步（`fx/hwcheck.js` 的 `hwcheckTriagePayload`） |
