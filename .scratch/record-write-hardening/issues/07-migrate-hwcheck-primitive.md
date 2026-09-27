# 07 — 收掉重复：`hwcheck_triage` 的私有原子写/锁迁到共享原语

**要做什么：** 现在全仓有**两份**同形的原子写 + 按路径锁实现——`atomic_io.py`（工单 01 新建）
与 `hwcheck_triage.py` 的私有副本。本单把后者换成前者，**行为与判据一字不变**
（既有测试就是这次的守卫）。

**被谁阻塞：** 01（共享原语）。

**状态：** ready-for-agent

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

- [ ] `write_hwcheck_record` 内部改调 `atomic_io.atomic_write_text`（**字节格式逐字不动**：
  `json.dumps(..., ensure_ascii=False, indent=2)` + 尾换行），删掉本模块的 `_TMP_COUNTER`。
- [ ] `_record_lock` 换成 `atomic_io.path_lock`（**语义等价**：键 = `normcase(abspath(path))`），
  删掉本模块的 `_RECORD_LOCKS` / `_RECORD_LOCKS_GUARD`；`update_hwcheck_record` 的形状与
  docstring 里那段"锁只护重读到落盘"的说明**保留**（它解释的是行为，不是实现细节）。
- [ ] **零行为变化**：`tests/test_hwcheck_triage.py` 与 `tests/test_hwcheck.py` 的既有用例
  一行不改、全绿（这是本单唯一的判据来源；如果为了让它们绿而改了测试，说明改坏了）。
- [ ] 反证（可选但推荐）：把 `path_lock` 的键改回不归一 → 既有并发/端点用例里应当有红；
  读数落盘。
- [ ] 顺带核一眼：`grep -rn "tmp-{os.getpid()}"` 全仓只剩 `atomic_io.py` 一处（收掉重复的硬判据）。

## 备注

- 本单**不改** `hwcheck_triage.py` 的任何对外契约（函数名、参数、返回、错误文案）。
- 若发现 `write_hwcheck_record` 的返回路径语义与共享原语不兼容（它返回 `Path`），
  在函数内保留返回值，不要改签名。
