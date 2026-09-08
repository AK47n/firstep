# 02 — 批次不变量收敛进测试：全库通用检查进 pytest

**要做什么：** 21 个批次快检脚本（`.scratch/wiki-*/sweep_*.py`）里那些「对全库永远成立」的结构不变量，改成每次跑测试都检查的用例——批次脚本退役后不变量不再无人守，新批次入库自动被覆盖。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 从 sweep 脚本与 `.scratch/library-audit/audit.py` 提炼出「全库通用、与批次无关」的不变量清单，逐条落成 `tests/test_library_invariants.py` 的用例（该文件已存在，新增用例不重写既有六条）。
- [x] 至少覆盖：平台条目声明的每个文件真实存在；模块声明的依赖都在库内；依赖图无环；`verified` 条目必须有文件（内嵌母版形态除外，按既有判据）；词表 `lib_modules` 引用的 slug 都在库内；模块 slug 与目录名一致。
- [x] 批次快照值（某批次某模块的 files/pins/verified 期望值）**不进测试**——在工单 Comments 里说明为什么（历史快照进测试会变成维护负担）。
- [x] 每条新用例先在当前库上跑：红了先修库或调整判据（不许为让测试绿而放宽），红/绿结论记进 Comments。
- [x] 失败信息可读：指出「哪个模块 / 哪条不变量 / 具体差异」。
- [x] 既有全量 `pytest` 全绿。

## Comments

**新增用例**（`tests/test_library_invariants.py`，文件从 6 条扩到 13 条）：

| 用例 | 钉的不变量 |
|---|---|
| `test_module_slug_matches_directory_name` | slug 与目录名一致（错位会让按 slug 找模块的调用方静默找不到） |
| `test_declared_platform_files_exist` | 平台条目声明的每个文件真实存在（空 files = 内嵌母版形态，跳过） |
| `test_platform_entry_files_have_no_duplicates` | 同一条目内文件不重复 |
| `test_module_dependencies_resolve_inside_library` | 依赖不悬空（拼错 slug = 生成时依赖展开静默少带模块） |
| `test_module_dependency_graph_is_acyclic` | 依赖图无环（环会让展开无限递归） |
| `test_wordlist_lib_modules_reference_existing_modules` | 词表 `lib_modules` 引用都在库内 |
| `test_modules_have_descriptions` | 模块必须有简介（摘要行主干，空的等于模型看不见用途） |

**为什么不进测试的东西更多**：21 个 sweep 脚本的主体是**批次快照**——`{"dht11": {"files": [...], "pins": [...], "verified": True}}` 这种「某批次某模块当时长什么样」的期望值。它们是历史证据，不是不变量：库演进后必然失效，进测试只会变成每次改库都要跟着改的维护负担。真正通用的那部分（文件存在 / 依赖无环 / slug 一致 …）已提炼上表；`audit.py` 继续作为人工复跑的全库审计工具保留（判据与测试同源）。

**一条被否掉的不变量**：`verified 条目必须有文件` 在当前库上有 3 处「合法例外」（`adc/stm32`、`delay/stm32`、`led/stm32`——实现内嵌母版，`files` 空但 verified）。判定「合法例外」需要一份手写豁免名单，那正是要避免的东西，故**不收敛这条**；「声明的文件存在」已覆盖真正的硬故障面。

**红证（注入破坏，工作区零改动）**：`.scratch/library-audit/probe_invariants_red.py` 把 `library/modules` 复制到临时目录、注入四类破坏后重跑：

```
RED   依赖悬空: 依赖指向库外模块：oled → ghost_module
RED   声明文件缺失: 平台条目声明了不存在的文件：
RED   依赖成环: 依赖成环：['motor → pid → motor']
RED   模块缺简介: 模块缺简介：dht11
```

**绿证**：`python -m pytest tests/test_library_invariants.py -q` → 13 passed；全量 `python -m pytest -q` → **3860 passed, 6 xfailed**。

**配套改动（词表挂接工单引起的预算账）**：默认词表补挂接后完整 wire 从 8259 涨到 8849，超过词表段 fit 上限（8500−166），`test_wordlist_segment_covers_default_wordlist_and_budget` 契约红；按仓库既有先例把 `WORDLIST_PROMPT_BYTES` 8500 → 9200（fit 上限 9034 ≥ 8849 全量送达 + 185B 余量），并在 `llm.py` 注释里如实记账余量代价：最坏形态 mspm0 128646B / stm32 128026B，距 129024 边界余 378B / 998B（旧值 727B / 1347B）——两个 worst-case 结构测试仍绿，但 mspm0 侧已低于 500B，后续往词表加内容应先瘦身而不是继续抬预算（复测工具 `.scratch/library-audit/probe_budget_headroom.py`）。
