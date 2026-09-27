# 03 — 资料库解包走共享原语：不留 `.update-tmp`、不互抢固定临时名

**要做什么：** 学生/维护者更新电赛资料库时，解包**失败不在库里留 `.update-tmp` 残渣**，
两个写者也不互抢同一个固定临时名；src/ 侧"手搓原子写"的站点再少一处。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-09-27；读数、双轴评审处置、账见文末）

## 结论（形状、读数、评审处置、账）

**形状。** `atomic_io` 把"临时名 + 换入 + 清残渣"收成一个实现 `atomic_write_via(path, write)`
（`atomic_write_text` 成了它的薄壳），`materials_apply._extract_zip` 改走它——**流式**不变
（仍是 `shutil.copyfileobj` 边读边写）、唯一临时名、失败清残渣；顺手把**同一条链上的
清单写回**（`.materials-manifest.json`）也换成原子写（那是这条链上唯一能留下**截断清单**的地方）。

**实测真值（本单的立论依据）**

| 项 | 收走前 | 现在 |
|---|---|---|
| 解包临时名 | `target.name + ".update-tmp"`（**固定**） | `f"{name}.tmp-{pid}-{计数}"`（唯一） |
| 写失败/换入失败 | 留 `.update-tmp` 残渣（无 `finally`） | 清残渣、原异常照抛 |
| 清单写回 | 裸 `write_text`（可留截断清单） | `atomic_write_text` |
| 结构守卫例外清单 | `materials_apply.py` 记 2 个站点 | **删掉**（站点归零，棘轮） |

**读数（本机实跑，全部 UTF-8 落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 定向 pytest | `python -m pytest tests/test_atomic_io.py tests/test_materials_apply.py tests/test_materials_update.py tests/test_materials_pack.py tests/test_materials_task.py -q` | **84 passed** | `probe-03-tests.txt` |
| 反证（三段） | `python .scratch/backlog-closeout/probe-03-red.py` | **PASS**：A 撤唯一临时名 → 1 条并发判据红；B 撤清残渣 → **7 条**残渣判据红（新旧入口 + 域层 + 清单）；C 解包退回手搓固定临时名 → 3 条红（域层两条 + 结构守卫）；逐条声明与实得全等、复原 sha256 逐字节、复原后 28 passed | `probe-03-red.txt` |
| mypy | `python -m mypy src/contest_generator/atomic_io.py src/contest_generator/materials_apply.py` | **Success**（收走了评审实测的 3 条新错：lambda 返回值不匹配 ×2 + `partial` 推不出 ×1） | 本段 |
| 全量 pytest | `python -m pytest -n auto -q` | **5650 passed + 11 skipped**（基线 5643 + 7 条新守卫/判据） | `probe-03-pytest.txt` |
| 结构守卫 | `python -m pytest tests/test_atomic_io.py -q` | 12 passed；例外清单剩 4 条（`codeview`/`recent_jobs`/`master_store`/`my_devices`），站点数与理由实测属实 | `probe-03-tests.txt` |

**双轴评审（2026-09-27，跑在工作树 vs `71dee2fc`）与处置。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Standards 硬① | **mypy 3 条新错**（`atomic_io:88,97` lambda 返回 int ≠ `Callable[[Path], None]`；`materials_apply:111` 默认参 lambda 推不出）——两文件在 HEAD 上本来是干净的 | **属实，已修**：`atomic_io` 改嵌套 `def`（带回 `None`），`materials_apply` 改 `functools.partial`；复跑 **mypy Success** |
| Spec ① | 判据②只做了**换入**失败——"注入**写失败** → 半截临时文件也要清"这一半没做（01 单同款缺口，两条入口都缺） | **属实，已补**：原语级 `test_atomic_write_via_write_failure_cleans_the_partial_tmp`（回调先真写半截再抛哨兵）+ 域层 `test_apply_write_failure_cleans_the_partial_tmp`（patch `materials_apply.shutil.copyfileobj`）——两段反证（B/C）都实测它们会红 |
| Spec 可能不对 | `materials_apply` 写回清单仍是**裸 `write_text`**：这条链上唯一能留下**截断清单**的地方 | **属实，已修**：改 `atomic_write_text` + 新判据 `test_apply_manifest_write_is_atomic`（占位目录逼失败 → 零杂散、占位目录不动）。**这是本单射程的扩张**（工单只说"解包"），理由：同一条链、同一类后果，且清单比单个文件更疼——记账在此 |
| Spec 可能不对 | `tools/update-app.py:208-220` 有**逐字同形**的固定 `.update-tmp` + 无 `finally`，而结构守卫只扫 `src/` | **属实，改票面**：那句"全仓再少一处"改为"**`src/` 侧**再少一处"，并如实记账——它是**独立脚本**（不 import `contest_generator`：它要在应用被替换前跑，那时包可能不在），守卫的扫描面本来就是 `src/`；**本单不动它**，已记进 `backlog.md`（另开单候选） |
| Standards 判断 | 新加的原语级并发用例 ≈ 既有那条逐行同形、钉同一实现（07 号单"两边钉的不是一件事"的理由在这不成立） | **属实，已删**：并发判据沿用既有 `test_concurrent_writes_share_no_tmp_file`（新入口是薄壳、共用同一实现；重复一条同形的是噪音）——探针 A 段照旧钉它 |
| Standards 坏味 | `atomic_write_bytes` 在 `src` **零调用点**（Speculative Generality） | **属实，已删**：本单只留实际被用到的 `atomic_write_via`（字节入口等有真调用方再加）。spec 与票面同步记账 |
| Spec 偏差 | spec 写"内部 `_atomic_replace`"，实现成**公开** `atomic_write_via` | **记账**：`materials_apply` 要跨模块用它，只能是公开 API；spec 已按实现更正 |
| Spec 缺 | 全量读数未落盘 | **已补**（上表最后两行） |

**账（留给后面的人）：**

1. **`tools/update-app.py:215` 的同款站点没修**（独立脚本，自己的固定 `.update-tmp` + 无 `finally`）：
   它是"应用替换器"，跑在应用被替换之前、不 import `contest_generator`；风险比 `src` 侧低一档
   （单次 CLI、应用已停服），但**中断留残渣**这件事一样成立。结构守卫的扫描面是 `src/`——
   要收它得先决定守卫要不要扫 `tools/`。已记进 `backlog.md`。
2. **`materials_apply` 的清单写回现在原子了，但它仍不是"事务"**：解包失败时已解出的文件
   会留在库里（靠调用侧的备份/断点语义兜着，本单不动这层）。
3. 守卫例外清单现在 **4 条**（`codeview` 4 站点 / `recent_jobs` 2 / `master_store` 3（目录换入）/
   `my_devices` 1（目录 staging））——都不是文件写，理由与站点数实测属实。

## 现状（实测，带 file:line）

- `src/contest_generator/materials_apply.py:103-106`（`_extract_zip`）：
  `tmp = target.with_name(target.name + ".update-tmp")` → 流式写入 → `os.replace(tmp, target)`。
  **固定临时名、无锁、无 `finally`**：两个写者抢同一个临时名；写失败/中断留下 `.update-tmp`。
- 它是 `record-write-hardening` spec 明确"没修"的站点（理由：解包被更新任务锁串行化、风险低一档）。
- **原语现状**：`src/contest_generator/atomic_io.py` 只有 `atomic_write_text`（写字符串）——
  解包写的是**字节流**（`shutil.copyfileobj`，资料库里有大文件，**不能改成先读进内存**），
  所以要给原语加一个"写字节 / 交给回调写"的入口。
- 结构守卫（`tests/test_atomic_io.py::test_only_one_atomic_write_implementation_in_src`）的例外清单里
  `materials_apply.py` 记着 **2 个站点**（造临时名 + 换入）——本单做完它归零，
  **按棘轮必须把那一条删掉**（守卫会点名"清单发霉"）。

## 验收标准

- [x] `atomic_io.py` 新增**字节/流式**入口（签名与语义写进 docstring），与 `atomic_write_text`
      共用同一份"临时名 + 换入 + `finally` 清残渣"实现（抽内部函数，**不复制第二份**）；
      既有 `atomic_write_text` 行为与字节格式**一字不变**（既有 7 条判据全绿）。
- [x] `materials_apply._extract_zip` 改走新入口：**仍是流式**（不吃内存）、仍是唯一临时名、
      失败/中断不留残渣、原异常照抛。
- [x] 域层用例（`tests/test_materials_update*.py` 或 `tests/test_atomic_io.py` 的既有家）：
      ① 解包成功后没有 `.update-tmp` / 任何杂散文件；② 注入写失败 → 无残渣 + 原异常照抛；
      ③ 并发解包不互抢（确定性做法照 `tests/test_atomic_io.py` 的 `SimpleNamespace` + `Event` 那套）。
- [x] 结构守卫例外清单删掉 `materials_apply.py` 那条；`python -m pytest tests/test_atomic_io.py -q` 绿。
- [x] 反证探针 `.scratch/backlog-closeout/probe-03-red.py`：撤唯一临时名 / 撤清残渣 → 对应判据红；
      逐条声明 + 与实得 `FAILED` 对账 + 复原 sha256 逐字节。
- [x] 读数落盘：定向 + 全量 `python -m pytest -n auto -q`。

## 备注

- 解包是**发版/更新链路**的一环：既有 `tests/test_materials_update*.py` 与
  `tests/test_full_update*.py` 是行为守卫，动它要连带跑（尤其"逐条目覆盖 + 备份 + 回滚"三条路径）。
- 与 `record-write-hardening` 的分工：那一批把**记录写**收口了；本单补的是**同一族里唯一的字节写**站点。
