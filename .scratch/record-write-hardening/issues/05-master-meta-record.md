# 05 — 母版元数据写加固：同平台并发导入不互抢临时文件、不留隐形残渣

**要做什么：** 同一平台连点两次「导入母版」（或一个导入 + 一个删除）时，
两个写者不许抢同一个固定临时名，库目录里也不许留下 `.{platform}.json.tmp`
——`list_masters` 跳过点开头的条目，这种残渣**没人会发现**。

**被谁阻塞：** 01（共享原语）。

**状态：** ready-for-agent

## 现状（实测，带 file:line）

- 写实现：`src/contest_generator/master_store.py:637-645`（`_write_meta`）——
  `temp = masters_dir / f".{meta.platform}.json.tmp"` → `os.replace(temp, target)`，
  **固定临时名、无锁、无 try/finally**；文件 = `<masters_dir>/<platform>.json`（`:639`）。
- **是整份重写，不是读-改-写**：唯一调用方 `import_master` 的 `:543`；写进去的 `meta` 是
  `:538-542` 现场造的（platform + sources + `analysis.warnings`），**不读旧 `{platform}.json`**。
  → 所以本单**不上合并**，只上「原语 + `finally` + 按路径锁」。
- 真实并发入口（都是同步 `def`，FastAPI 放线程池；服务是单进程 `uvicorn.run`）：
  `POST /api/masters/import`（`webapp.py:5726-5740` → `import_master_direct` → `import_master`）、
  `POST /api/masters/confirm`（`webapp.py:5635-5676` → `confirm_distillation` → `import_master`）。
  覆盖 `masters_dir` 的锁**不存在**（`_generation_guard` 与母版无关）。
- 同一份文件还有第二个写者：`delete_master`（`:602-610`）——`:606` 删目录、`:609`
  `unlink(missing_ok=True)` 删 meta，**同样无锁**，要和 `_write_meta` 归同一把锁。
- 既有测试：`tests/test_master_store.py` 无 `.tmp` / 并发 / 残渣用例；
  **结构钉**：`tests/test_autocommit.py:393-412` 把 `_write_meta(` 登记为写原语
  （管自动提交挂点，不管并发）——本单**不改签名**，但要核对这条钉仍是绿的。

## 验收标准

- [ ] `_write_meta` 改走 `atomic_io.atomic_write_text`（**字节格式逐字不动**：
      现在是 `json.dumps(..., ensure_ascii=False, indent=2)` 且**没有尾换行**——这条最容易改坏），
      并有 `finally` 清残渣；清理失败不掩盖原异常。
- [ ] `_write_meta` 与 `delete_master` 的 meta 删除**归同一把 `path_lock(target)`**。
- [ ] 并发用例（`tests/test_master_store.py`）：两个线程同平台写 →
      ① 无异常；② 库目录里**没有任何点开头的临时文件**（`iterdir` + 逐条断言，别用 `glob("*.tmp")`）；
      ③ 最终 meta 是合法的其中之一、JSON 可解析。
- [ ] 失败注入用例：`replace` 抛错 → 无残渣 + 原异常照抛（现在这条会留 `.{platform}.json.tmp`）。
- [ ] 与 `delete_master` 交错：只断言「不留残渣 + 文件状态自洽（要么有合法 meta、要么没有）」，
      **不**断言语义级优先级（删除与导入谁赢不在本单射程，写进票的「不做」段）。
- [ ] 端点级用例（`tests/test_webapp.py`，家 = `:4547`/`:4568`/`:4580` 附近）：并发
      `POST /api/masters/import` 同平台 → 判据取最终盘上 meta 与目录存在性；撤锁注入下实测变红。
- [ ] `tests/test_autocommit.py` 的写原语登记核对结论写进票（绿 = 签名没变；若红，说明 `_write_meta`
      的调用形态变了，要在票里说明怎么改的）。
- [ ] 反证探针 `.scratch/record-write-hardening/probe-05-red.py`（逐条声明 + 对账）。
- [ ] 读数落盘：定向 + 全量 `.txt`。

## 不做

- 不做「同平台并发导入的语义仲裁」（后到者赢 / 拒绝 / 排队）——那是产品决策，
  且需要先回答"两个导入同时改母版目录"这件事本身合不合理。本单只保证原子性、不互抢、不留残渣。
