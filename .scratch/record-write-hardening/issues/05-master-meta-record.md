# 05 — 母版元数据写加固：同平台并发导入不互抢临时文件、不留隐形残渣

**要做什么：** 同一平台连点两次「导入母版」（或一个导入 + 一个删除）时，
两个写者不许抢同一个固定临时名，库目录里也不许留下 `.{platform}.json.tmp`
——`list_masters` 跳过点开头的条目，这种残渣**没人会发现**。

**被谁阻塞：** 01（共享原语）。

**状态：** resolved（2026-09-27；读数、双轴评审处置、残留记账见文末）

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

- [x] `_write_meta` 改走 `atomic_io.atomic_write_text`（**字节格式逐字不动**：
      现在是 `json.dumps(..., ensure_ascii=False, indent=2)` 且**没有尾换行**——这条最容易改坏），
      并有 `finally` 清残渣；清理失败不掩盖原异常。
- [x] `_write_meta` 与 `delete_master` 的 meta 删除**归同一把 `path_lock(target)`**。
- [x] 并发用例（`tests/test_master_store.py`）：两个线程同平台写 →
      ① 无异常；② 库目录里**没有杂散文件**（`iterdir` + 逐条断言，别用 `glob("*.tmp")`）；
      ③ 最终 meta 是合法的其中之一、JSON 可解析。
- [x] 失败注入用例：`replace` 抛错 → 无残渣 + 原异常照抛（收走前会留 `.{platform}.json.tmp`）。
- [x] 与 `delete_master` 交错：只断言「不留残渣 + 文件状态自洽（要么有合法 meta、要么没有）」，
      **不**断言语义级优先级（删除与导入谁赢不在本单射程）。
- [x] 端点级用例（`tests/test_webapp.py`，家 = `:4547`/`:4568`/`:4580` 附近）：导入与删除并发 →
      判据取最终盘上 meta 与目录存在性；撤锁注入下实测变红。
- [x] `tests/test_autocommit.py` 的写原语登记核对结论：**绿**（15 passed，
      `_write_meta(` 仍是写原语标记、`import_master` 那一格仍是 commit；签名没变，没改登记表）。
- [x] 反证探针 `.scratch/record-write-hardening/probe-05-red.py`（逐条声明 + 对账；**三段**）。
- [x] 读数落盘：定向 + 全量 `.txt`。

## 结论（读数、评审处置、账）

**形状。** `_write_meta` 的落盘改走 `path_lock(target)` + `atomic_io.atomic_write_text`
（唯一临时名 + `finally` 清残渣）；`delete_master` 删 meta 那一步**进同一把锁**；
`import_master` 的整份重写形状与目录换入逻辑**一字未动**（这里不读旧文件，所以不上"读-改-写"）。

**不变量核对**：读侧中文文案未动；meta 字节格式**逐字节相同**——实测同一份 meta 分别走
收走前的手搓固定临时名实现与本单实现，落盘 107 B 完全一致（`…\r\n}`，**没有**尾换行）；
`_write_meta` 签名与调用点未变（`tests/test_autocommit.py` 的写原语登记因此仍是绿的）；
`materials_apply` / `recent_jobs` / `codeview` / `hwcheck_triage` 未碰。

**读数（本机实跑，全部 UTF-8 落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 定向 pytest | `python -m pytest tests/test_master_store.py tests/test_webapp.py -q` | **450 passed** | `probe-05-tests.txt` |
| 反证（三段） | `python .scratch/record-write-hardening/probe-05-red.py` | **PASS**：A 撤掉"同一把锁" → 删除交错（域层 + 端点）两条红；B 撤共享原语的清残渣（唯一临时名 → 点开头固定名、`finally` → `pass`）→ "写失败留残渣"一条红；C 撤回收走前的完整形状（锁 + 唯一临时名一起撤）→ 并发互抢 + 删除交错 + 端点三条红。逐条声明与实得 `FAILED` 完全一致、每段复原 sha256 逐字节相同、复原后 450 passed | `probe-05-red.txt` |
| 写原语登记守卫 | `python -m pytest tests/test_autocommit.py -q` | **15 passed**（签名没变，登记表不用动） | 见上表定向读数 |
| 全量 pytest | `python -m pytest -n auto -q` | **5636 passed + 11 skipped / 112.68s**（上一单基线 5631 + 11 → 本单 +5 条用例） | `probe-05-pytest.txt` |

**双轴评审（2026-09-27，`code-review` 跑在工作树 vs 固定点 `17b2249f`）与处置。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Spec (c)① / Standards 硬② | **悬空 meta 仍可达**（评审实测复现）：`import_master` 的**目录换入**在锁外，与 `delete_master` 的 `delete_entry` 之间有一条窄缝 → 终态"有 meta、没目录" | **属实**：spec 把本单的锁范围定在"meta 写 + meta 删除"两点，**扩到目录换入不在本单射程**；处置 = 把声明**收严**（`delete_master` 与端点用例的 docstring 都明写"只护 meta 这一个文件本身"）+ 落账第 1 条 → **留给工单 06 定夺**（06 的「前置小账」第 5 条） |
| Spec (a)③ | 端点级原句是"并发 `POST /api/masters/import` 同平台"，实做的是 import × delete | **记账不补**：唯一临时名之下两条同平台导入不再互抢（撤锁也不红），而它们的**目录换入**是 spec 明写"不做语义仲裁"的那一档 → 端点判据改钉"删除与写 meta 互斥"，票面已如实说明（见账第 2 条） |
| Standards 硬① | **记账断链**：工单 04 承诺"`_run_in_thread` 三份收成一处记进工单 06"，但 06 没这条；本单又添**第四份**逐字复制 | **属实，已修**：工单 06 的验收标准补了「前置小账」五条（helper 收一处 / `atomic_io` docstring 过期 / 04 的两条残留 / 05 这条窄缝），本单不再单独挂账 |
| Standards 判断③ | "残渣没人发现"归因不准——`list_masters` 同行还跳过"非目录"条目 | **属实，已修**：docstring 改成"`not entry.is_dir()` 与点开头**都**跳过" |
| Standards 判断④ | 端点新用例的线程没带 `errors` 表（抛错只报 `KeyError`） | **属实，已修**：补 `errors` 收集 + `assert errors == []`（与域层同形） |
| Standards 判断⑤ | `atomic_io.py` docstring 里「本批的调用方都在各域的 `update_*` 里持锁」对 05 已不成立（`_write_meta` 是整份重写、直接持锁） | **排进工单 06**：动 `atomic_io.py` 会让 01–04 已提交读数里绑的 sha256 变旧，而 06 本来就要重跑全部探针读数 → 在那里一次改一遍跑（06「前置小账」第 2 条） |
| Spec ①② / Standards 硬③ | 票未翻牌、验收框全空、无结论段；全量读数未落；`test_autocommit.py` 核对结论未进票 | **属实**：本段补齐（翻 `resolved` + 勾选 + 读数表 + autocommit 结论那一条） |

**账（留给后面的人 / 工单 06）：**

1. **目录换入 × 删 meta 的窄缝（本单没封死）**：本单的锁只护 `{platform}.json` 这一个文件，
   `import_master` 的目录换入（`master_store.py:519`，中间还夹着 `rmtree(backup_dir)`）
   在锁外。评审按"导入钉在目录换入之后、删除先跑完"的时序**实测复现**：终态目录没了、
   meta 还在（`list_masters` 看不见它，也就没人清）。要闭得把锁提到目录换入之前，
   并把 `delete_master` 的 `delete_entry` 也包进来——那已经越过本单"只改 meta 写"的边界
   （而且要考虑 rmtree 期间持锁的代价）→ **留给工单 06 定夺**。
2. 本单端点级判据钉的是"**删除与写 meta 互斥**"这一种交错；两条同平台 `POST /api/masters/import`
   的端点用例**没立**——唯一临时名之下它们不再互抢（撤锁也不红），而目录换入那一档的
   并发语义 spec 明写不做仲裁。如实记账，不假装覆盖。
3. `_run_in_thread` 在本批已有四份逐字复制（`test_drafts` / `test_idea_chat` / `test_params` /
   `test_master_store`）→ 收成一处记在工单 06 的「前置小账」第 1 条。

## 不做

- 不做「同平台并发导入的语义仲裁」（后到者赢 / 拒绝 / 排队）——那是产品决策，
  且需要先回答"两个导入同时改母版目录"这件事本身合不合理。本单只保证原子性、不互抢、不留残渣。
