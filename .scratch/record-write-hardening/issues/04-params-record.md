# 04 — 参数表写加固：刷新路径不许把扫描刚写的新表盖回旧快照

**要做什么：** 学生应用一次参数值后表被刷新，同时参数扫描刚写进一张新表——
**新表不许被盖回旧快照**；写失败留意（刷新路径现在静默吞 `OSError`，残渣没人报）也不留垃圾文件。

**被谁阻塞：** 01（共享原语）。

**状态：** ready-for-agent

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

- [ ] `params.py` 新增 `update_params(output_dir, merge: Callable[[ParamList], ParamList]) -> ParamList`；
      `write_params` 内部改走 `atomic_io.atomic_write_text`（字节格式逐字不动）。
- [ ] `_persist_applied_param` 的落表改走 `update_params`（在**最新**盘上重放单参数刷新），
      **保留**「写盘失败不阻断主流程」的口径（吞 `OSError` 的语义不变，票里写明为什么保留）。
- [ ] `run_param_scan` 的 `412` 保持整份替换（不读旧表 → 不上合并），只换写实现。
- [ ] 域层用例（`tests/test_params.py`）：① 原子写无残渣；② 写失败无残渣 + 原异常；
      ③ 并发写不互抢；④ **交错不丢**：刷新路径读完之后、写之前，另一笔整份写入新表 →
      刷新不许把新表盖回旧快照（这条是本单的主判据，判据取最终盘上内容）。
- [ ] 端点级用例（`tests/test_params.py` 或 `tests/test_webapp.py` 的既有参数端点附近）：
      apply 的落表与扫描写入并发，判据取最终落盘；撤锁注入下实测变红。
- [ ] 反证探针 `.scratch/record-write-hardening/probe-04-red.py`（逐条声明 + 对账）。
- [ ] 读数落盘：定向 + 全量 `.txt`。

## 备注

- 空表不落盘的既有契约（`params.py:409-412` 注释：无文件 = 未识别过）**不许变**。
- `_refresh_param_after_apply` 是纯函数，合并闭包里复用它，别在合并里重写逻辑。
