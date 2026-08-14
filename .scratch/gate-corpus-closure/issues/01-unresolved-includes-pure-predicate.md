# 01 — 门禁闭包世界：第六道 unresolved_includes 对活盘 stat，违背「门禁只吃语料」契约

**What to build:** `_check_unresolved_includes`（`generator.py:756-801`）第 792 行对每个 include 候选 `(d / header).is_file()` stat 活盘——六道门禁里唯一闭包不了语料的一道。ModuleCorpus 契约三处文字（`generator.py:430`「门禁只吃语料，不再碰盘」、:447「测试可内存构造直喂门禁」、门禁 docstring :764「门禁只吃语料不碰盘」）当前是假话：内存直构语料无法忠实覆盖第六道，产物体外验收也得 stat 真实母版/工具链目录。修复后契约文字成真——语料构建时一次扫盘，门禁退化为纯集合成员判定。

**Status:** ready-for-agent

## 现状证据（2026-08-14 读码核实）

- `generator.py:792`：`if any((d / header).is_file() for d in (own_dir, *search_dirs))`——search_dirs = master_search_dirs（母版 IncludePath，:766）+ 各模块 own_dir（:768-773）；own_dir = main.c 的母版根 / 模块文件所在库目录。
- 语料已有但没用上：模块文件（按 own_dir 分组即可得兄弟文件名）+ `master_headers`（母版树全部 *.h 相对路径，:497-507）——own_dir 与母版树内解析完全可以在语料内判定；缺的只有母版 IncludePath 指向的目录的 *.h 名单。
- 豁免集合（`_LIBC_HEADERS | external_headers`，:777）不受影响。
- 语义保持要求：Windows `is_file` 大小写不敏感（名集合须小写化对齐）；搜索目录不存在 = 解析失败（与现 is_file 返回 False 一致）；报错文案逐字不变。

## 设计定案（已代决，实施会话不再重开）

1. **`ModuleCorpus` 增字段** `search_dir_headers: tuple[tuple[Path, frozenset[str]], ...]`——每个 master_search_dir 的 *.h 基名集合（小写化），`build_module_corpus` 构建时对每个搜索目录 glob 一次（目录不存在 → 空集）。own_dir 兄弟解析用**语料内已有**数据：模块文件按 own_dir 分组取基名 + `master_headers` 按父目录分组取基名——不新增扫描。
2. **门禁改纯成员判定**：`header.lower()` ∈ own_dir 兄弟名集合 ∪ 各搜索目录名集合 ∪ 豁免集合 → 放行；否则报错（文案逐字不变）。整个谓词零盘访问。
3. **`build_output_tree_corpus`（`generator.py:521`）同步填充新字段**（产物树侧重建同一语料——验收脚本与门禁同源，字段形状必须同构）。
4. 契约文字（:430/:447/:764）不动——修复让它们成真。

## 实施边界

- src：只动 `src/contest_generator/generator.py`。
- tests：只动 `tests/test_generator.py`。
- **零改动**：llm.py / fix_errors.py / webapp.py / index.html / generate_check.py / selection.py / compile_runner.py——本工单不碰（并行工单文件边界）。

## 验收标准

- [ ] 红证先行：新测试 monkeypatch `Path.is_file` 抛 AssertionError（证明门禁零盘访问）跑第六道 → 现行必红（:792 调 is_file）→ 实施后绿
- [ ] 内存直构测试：语料含 search_dir_headers 而搜索目录在盘上不存在 → 门禁照常放行（纯语料判定）
- [ ] 既有门禁测试全绿（报错文案逐字不变）+ 全量 pytest 绿（基线 1369）+ `mypy src` 干净
- [ ] （推荐）真机回归：`python .scratch/real-run/generate_check.py` 2026C `--reuse-recommend` 门禁全过不误杀（缓存路径成本可控）
- [ ] `git status` 只出现预期文件

## 实施提示词（新会话粘贴）

> 工单：`.scratch/gate-corpus-closure/issues/01-unresolved-includes-pure-predicate.md`（先读全文，设计已定案勿重开）。
> 环境：`cd C:\Users\luoji\Desktop\firstep` → `git worktree add ../firstep-wt-gate-corpus -b gate-corpus-closure-01` → `cd ../firstep-wt-gate-corpus`（必须独立 worktree，主检出有并行工单）。
> 文件边界：只动 `src/contest_generator/generator.py` + `tests/test_generator.py`；其余 src 文件一个都不碰（并行工单在改 llm.py / generate_check.py）。
> 关键：build_output_tree_corpus 与 build_module_corpus 两处语料同构（字段形状一致）；报错文案逐字不变；Windows 大小写不敏感语义用小写化名集合保持。
> 验收：红证（is_file monkeypatch 跑红记录）→ 实施绿 + 内存直构测试 + 全量 pytest 绿 + `mypy src` 干净 +（推荐）真机 generate_check 回归；提交格式 `refactor: ...（工单 gate-corpus-closure/01，N 绿 + mypy src 干净——...）` + docs 一笔；`gh pr create --body-file`；不 force push；证据写本文件 Comments，Status → resolved，推送。

## Comments
