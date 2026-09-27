# 07 — 收掉重复：`hwcheck_triage` 的私有原子写/锁迁到共享原语

**要做什么：** 现在全仓有**两份**同形的原子写 + 按路径锁实现——`atomic_io.py`（工单 01 新建）
与 `hwcheck_triage.py` 的私有副本。本单把后者换成前者，**行为与判据一字不变**
（既有测试就是这次的守卫）。

**被谁阻塞：** 01（共享原语）。

**状态：** resolved（2026-09-27；读数、双轴评审处置、"一行不改"的实情见文末）

**来源**：双轴评审 2026-09-27 的 Standards 轴点名——工单 01 自称"纯 expand"，
spec 把迁移写成"另开单再说"却没给单号，工单 06 的白名单又把这个私有副本合法化，
**等于没有收口步**，两份实现会长期并存（docstring 与测试脚手架也是同一套照抄）。

## 现状（实测，带 file:line）

- 私有副本：`src/contest_generator/hwcheck_triage.py:896-919`（`write_hwcheck_record` 的唯一临时名 +
  `finally` 清残渣）、`:387-406`（`_RECORD_LOCKS` / `_RECORD_LOCKS_GUARD` / `_record_lock`）、
  `:80`（`_TMP_COUNTER`）、`:409-425`（`update_hwcheck_record`，形状保留）。
- 共享原语：`src/contest_generator/atomic_io.py`（工单 01）。
- 守卫（本单必须保持全绿）：`tests/test_hwcheck_triage.py:554-690`
  （原子写不留残渣 / 写失败不留残渣 / 并发不互抢 / 读-改-写不丢字段 / 旧快照不覆盖新值）、
  `tests/test_hwcheck.py:3278`、`:3343`（端点级）。

## 验收标准

- [x] `write_hwcheck_record` 内部改调 `atomic_io.atomic_write_text`（**字节格式逐字不动**：
  `json.dumps(..., ensure_ascii=False, indent=2)` + 尾换行），删掉本模块的 `_TMP_COUNTER`。
- [x] `_record_lock` 换成 `atomic_io.path_lock`（**语义等价**：键 = `normcase(abspath(path))`），
  删掉本模块的 `_RECORD_LOCKS` / `_RECORD_LOCKS_GUARD`；`update_hwcheck_record` 的形状与
  docstring 里那段"锁只护重读到落盘"的说明**保留**（它解释的是行为，不是实现细节）。
- [x] **零行为变化**：`tests/test_hwcheck_triage.py` 与 `tests/test_hwcheck.py` 的**断言**
  一行未改、全绿（见下面"一行不改"的实情：只挪了并发用例的**注入点**）。
- [x] 反证（本批每单都做）：三段机制反证落在**既有用例**上——撤锁 / 撤唯一临时名 / 撤清残渣
  各有红；读数落盘。
- [x] 顺带核一眼：`grep -rn "tmp-{os.getpid()}"` 全仓**只剩 3 处**——`atomic_io.py:65`（原语自己）
  与 `codeview.py:362/532`（本批白名单里的 pid 后缀那一处，spec 范围外）；**`hwcheck_triage`
  那份已收掉**（工单原句写"只剩 atomic_io 一处"，判据本身写错了，见下）。

## 结论（形状、读数、评审处置、"一行不改"的实情）

**形状。** `write_hwcheck_record` → `atomic_io.atomic_write_text`（唯一临时名 + `finally` 清残渣）；
`_record_lock` → `atomic_io.path_lock`；本模块的 `_TMP_COUNTER` / `_RECORD_LOCKS` /
`_RECORD_LOCKS_GUARD` 与随之不再需要的 `import os` / `import itertools` / `import threading`
（最后那个是评审抓到的漏删）都删了；`update_hwcheck_record` 的形状与那段"锁只护重读到落盘"
的 docstring 逐字保留；`atomic_io.py` **零字节改动**（评审复核）。

**"既有用例一行不改"的实情（逐行列账，不含糊）。** 断言**一字未动**；改的只有**注入点**——

| 改动 | 行数 | 为什么 |
|---|---|---|
| `from contest_generator import atomic_io, hwcheck_triage` | 1 | 判据要打到"写实现真正所在的那个模块"上 |
| 用例 docstring 补一句（写实现归共享原语后，目标模块就是 `atomic_io`） | 2 | 让下一个人知道为什么打在这里 |
| `monkeypatch.setattr(hwcheck_triage, "os", …)` → `atomic_io, "os"` | 1 | 写实现搬家了，注入点跟着搬 |
| 那行上方的注释 | 1 | 同上 |
| （`real_replace = os.replace` 等**未动**） | — | 判据与顺序钉法原样 |

共 **1 + 2 + 1 + 1 = 5~6 行**，**判据（断言集合）零改动**，且撤掉"唯一临时名"时这条用例**照样红**
（探针 B 段）——所以不算削弱判据（双轴评审核过：全仓再无第二处注入 `hwcheck_triage.os`
或引用刚删掉的私有物）。

**工单那条 grep 判据本身写错了**：`tmp-{os.getpid()}` 在 `codeview.py:362/532` 也命中
（本批白名单里的 pid 后缀站点、spec 范围外），实测全仓 **3 处**；本单真正收掉的是
`hwcheck_triage` 那一份——它的手搓站点归零，`tests/test_atomic_io.py` 的例外清单里那条
按棘轮当场删掉（守卫会点名"清单发霉"）。

**已知偶发（不是本单引入，别误判）。** `test_concurrent_record_writes_share_no_tmp_file`
在**负载下**会以 `PermissionError(13, 拒绝访问)` 红：两个线程对**同一目标**并发真实
`os.replace` 时 Windows 会拒绝（`atomic_io.py` docstring 里记着这条实测）。评审用同一编排
在固定点与工作树上交替各跑 400 次做对照：**老 25/400（6.3%） vs 新 30/400（7.5%）**，
无统计差别；空闲时复跑两个文件 **187 passed** 全绿。要根治得给那条用例的两次真实替换
排序（本批 02–05 的新并发用例就是这么写的）——属另开单，不在本单射程。

**读数（本机实跑，全部 UTF-8 落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 定向 pytest | `python -m pytest tests/test_hwcheck_triage.py tests/test_hwcheck.py -q` | **187 passed**（既有用例，断言一字未改） | `probe-07-tests.txt` |
| 反证（三段） | `python .scratch/record-write-hardening/probe-07-red.py` | **PASS**：A 撤临界区 → 域层"不丢字段"+ 端点"两处入口串行"两条红；B 撤唯一临时名 → "并发不抢临时名"红；C 撤清残渣 → "写失败不留残渣"红。逐条声明与实得 `FAILED` 完全一致、每段复原 sha256 逐字节相同、复原后回绿 | `probe-07-red.txt` |
| 全量 pytest | `python -m pytest -n auto -q` | **5639 passed + 11 skipped / 114.46s**（与 06 收口同一基线：本单零行为变化、零新增用例） | `probe-07-pytest.txt` |
| 结构守卫 | `python -m pytest tests/test_atomic_io.py -q` | **9 passed**（`hwcheck_triage` 那条例外已按棘轮删掉） | 见批尾读数 |

**双轴评审（2026-09-27，`code-review` 跑在工作树 vs 固定点 `fd8d2645`）与处置。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Standards 判断① | **Dead Code**：`hwcheck_triage.py` 的 `import threading` 迁后无人用（`os` / `itertools` 删了、它漏删） | **属实，已修**（本批唯一真遗留；改完复跑定向与探针） |
| Spec (a)① | "既有两个文件一行不改、全绿"**字面不成立**（实测 5~6 行：import + 用例 docstring + 注释 + setattr 目标） | **属实**：本段逐行列账，不直接打勾——断言零改动、且探针 B 段证明撤修照样红 |
| Spec (a)② | 工单那条 `grep "tmp-{os.getpid()}"` 判据**自己写错**（`codeview.py:362/532` 也命中，实测 3 处） | **属实，已修**：验收条款按实测改写（3 处，其中本单收掉的是 hwcheck 那份） |
| Spec (c) | 并发用例在负载下会以 `PermissionError(13)` 偶发红——**非本单引入**（老/新各 6.3% / 7.5%，400 次对照无差别） | **属实**：本段如实记账 + 写进 `local-environment` §0（下一个人别误判成这批的缺陷） |
| Spec (a)④ | 本单改了 `tests/test_atomic_io.py` → probe-01 绑的 sha 失效，必须重跑 01–06 汇总 | **已做**：收口轮的汇总脚本重跑过全部探针读数（`probe-06-red-summary.txt` 头部记着 HEAD 与工作树状态） |
| Standards 判断② | 重复押注：迁移后本用例与 `tests/test_atomic_io.py` 同名用例注进同一处（都打 `atomic_io.os`） | **记账不改**：两边钉的不是同一件事（那边是原语契约本身、这边是"检测记录这条调用链真的走了它"），重复是有意的双保险 |

## 备注

- 本单**不改** `hwcheck_triage.py` 的任何对外契约（函数名、参数、返回、错误文案）。
- 若发现 `write_hwcheck_record` 的返回路径语义与共享原语不兼容（它返回 `Path`），
  在函数内保留返回值，不要改签名。
