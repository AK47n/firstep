# 01 — 架构深化 v5：master.py 三轴拆块——类别生命周期 / 蒸馏编排 / 母版库 CRUD（候选 3，Strong）

**What to build:** 第五轮架构深化（2026-08-09 grilling 共识，候选 3，源自 architecture-review-20260809-102431）。master.py（1386 行）是七职责杂烩："启动文件去重"与"工程配置文件"两条概念各散 8 个不相邻站点，读懂一条要读大半个文件；RULE_CATEGORIES 表泛化停了一半（`_validate_forced_exclusions` 单调用残留，docstring 自认）。拆三轴：**categories.py**（文件类别生命周期 + 启动钩子全收）/ **master.py 瘦身**（扫描 / 对比 / 蒸馏编排 / 验证门）/ **master_store.py**（母版库 CRUD + MasterMeta + MasterError）。纯搬家，行为零变化，错误文案逐字不变。

1. **新建 `src/contest_generator/categories.py`**（文件类别生命周期唯一出处，语义逐字搬移）：
   - 规则定义：`RESIDUE_RULES` / `residue_reason`、`BINARY_PROBE_BYTES` / `BINARY_FILE_REASON` / `_is_binary_file` / `_binary_reason`、`MAIN_C_TEMPLATE_REASON` / `main_c_reason`、`INFRASTRUCTURE_SUFFIXES` / `INFRASTRUCTURE_REASON` / `infrastructure_reason`、`UVPROJX_CONFIG_REASON` / `CCS_CONFIG_REASON` / `CONFIG_FILE_SUFFIXES` / `config_file_reason`、`STARTUP_REPLACEMENT_REASON`、`RuleCategory` / `RULE_CATEGORIES`（判例 docstring 全保留）；
   - **`classify(rel: str, path: Path) -> tuple[str | None, bool]`**（新接口，Q7 裁决）：表内第一命中返回 (类别 key, 是否启动候选)；启动候选 = key == "infrastructure" 且 `is_startup_candidate(rel)`。表遍历知识收进本模块，scan 不再自写循环；
   - 启动生命周期：`_pick_startup(startup_files: Sequence[str]) -> str | None`（签名收窄，不再吃 ProjectComparison）；`_validate_startup_disposition(report, startup_files)`（Q6 裁决：跟启动走）；**`_validate_forced_exclusions` 并入 `_validate_startup_disposition` 后删除**；
   - import：keil（`is_md_startup` / `is_startup_candidate`）、report（`ACTION_EXCLUDE`）、master_store（`MasterError`）。
2. **新建 `src/contest_generator/master_store.py`**（母版库 CRUD + 域错误定义处）：`MasterError`、`MasterMeta`（+ `to_dict` / `from_dict`）、`StructureAnalysis`、`master_project_dir`、`analyze_structure` / `_validate_keil_structure`、`import_master` / `list_masters` / `get_master` / `delete_master`、`_write_meta`、`_validate_store_key` / `_validate_known_platform`、`_require_str` / `_require_str_list`。import：keil（`validate_project_structure` 等）、treewalk、platforms、entry_store、categories 不 import（见 4）。
3. **master.py 瘦身**（只留扫描 / 对比 / 判定素材 / 蒸馏编排 / 验证门 / 确认事务）：删除全部迁出定义，改 import categories + master_store；`scan_project` 的类别循环改 `key, is_startup = classify(rel, path)`；`assemble_report` / `_render_inputs` 的 `_pick_startup(comparison)` 改 `_pick_startup(comparison.startup_files)`；`main_c_template` / `TEMPLATES_DIR` 留 master（Q4①：编排的渲染输入，被 assemble / apply / confirm 三处用）；`ProjectStructure` / `ProjectComparison` / `build_judgment_files` / `build_comparison_summary` / 五个验证门（`_validate_report` / `_validate_category_disposition` / `_validate_merge_sources` / `_validate_platform_match` / `_validate_judgment_coverage`）/ `_source_project` / `apply_distillation` / `confirm_distillation` 全留 master（Q4③④）。
4. **裁决修正一处（grilling Q4② 的环修正）**：`PLATFORM_CONFIG_FILES` **随唯一消费者 `analyze_structure` 进 master_store.py**，不进 categories——原裁决说随类别，但读代码发现：categories 需 import master_store 的 `MasterError`（启动验证用），若 master_store 又 import categories（取 PLATFORM_CONFIG_FILES）则成环。修正后依赖图无环：master_store → {keil, treewalk, platforms, entry_store}；categories → {keil, report, master_store}；master → {categories, master_store, keil, ccs, entry_store, report, treewalk}。类别概念部分（`config_file_reason` / `CONFIG_FILE_SUFFIXES`）仍进 categories。
5. **import 指向全量迁移**（grep 全扫，零残留）：src 侧 archive.py（`MasterError` → master_store，`ProjectComparison` 留 master）、errors.py（`MasterError` → master_store）、generator.py（`master_project_dir` → master_store）、webapp.py（`import_master` / `delete_master` / `list_masters` → master_store，`confirm_distillation` / `distill_master` / `scan_project` 留 master）；tests 侧 test_master.py 的 import 大块（18-40 行）按名分家、test_generator.py:36 / test_reference_library.py:27 / test_webapp.py:52 / test_errors / fakes.py / conftest.py 随迁移。**不 re-export**（Q4⑤）：master.py 不留转发名。
6. **测试迁移 + 结构测试**：新建 `tests/test_categories.py` / `tests/test_master_store.py`（用例随迁，不新增语义断言）；test_master.py 保留蒸馏用例。结构测试（防回退，先例 errors.py 防漏登）：断言 `master.RULE_CATEGORIES is categories.RULE_CATEGORIES`（master 只消费不定义），且 master 模块无任何规则函数定义（`not hasattr(master, "residue_reason")` 等四条）。
7. **CONTEXT.md 词表更新**（同批提交）：「文件类别」主要实现列 → categories.py（RuleCategory / RULE_CATEGORIES / classify，唯一出处）；「启动文件」主要实现列 → keil.py（格式）/ categories.py（去重生命周期）；「母版」主要实现列 → master.py（蒸馏编排）/ master_store.py（母版库 CRUD 与元数据）；「架构要点」文件类别生命周期单源化 bullet 补"类别表与 classify 收进 categories.py，master 只消费"。

**明确不动的（边界，勿越）**：蒸馏行为与全部错误文案逐字不变（既有断言原样过）；启动去重不升格表内 citizen（Q3 裁决）；平台适配接缝（候选 4）与 llm 栈收敛（候选 2）不做；keil.py / ccs.py / llm.py / selection.py / generator 业务逻辑零改动（generator 只有 import 行变化）；母版元数据仍放目录外兄弟 json（master.py 文档承重决策：母版目录被生成器整体复制，内部带 json 会污染生成工程）——entry_store 族布局不动，本轮只复用原语不迁移布局；webapp 路由零改动。

**Status:** resolved（2026-08-09 合入 main f9088d0，801 绿 + mypy 干净，PR #18）

## 验收

- [x] 全量 pytest 绿（基线 800）+ mypy 干净；错误文案断言原样过（行为零变化）
- [x] grep：`residue_reason|main_c_reason|infrastructure_reason|config_file_reason|RULE_CATEGORIES|classify` 在 src 唯一出处 = categories.py；`MasterError|MasterMeta|import_master|list_masters|get_master|delete_master|master_project_dir|analyze_structure` 唯一出处 = master_store.py（消费点 import 不算）
- [x] `_validate_forced_exclusions` 全库无结果（已并入启动验证）；`_validate_startup_disposition` 在 categories.py
- [x] 结构测试过：master 只消费不定义（`is` 恒等 + 四条 not hasattr）
- [x] `grep -rn "from \.master import" src tests` 的每一条 import 名都能在（master 或 master_store）找到落点，无死 import
- [x] CONTEXT.md 词表四处更新到位

## 实施提示词（新会话用）

```
工单：.scratch/architecture-deepening-v5/issues/01-master-decompose.md（架构深化 v5：master.py 三轴拆块，候选 3）

先读工单全文，按 1-7 节执行。独立 worktree（勿在主检出改）：
git worktree add ../firstep-v5-01 main

1. 新建 categories.py / master_store.py：按工单 1/2 节逐字搬移（docstring 与判例全保留，语义零变化）
2. master.py 瘦身（工单 3 节）：删迁出定义；scan_project 类别循环改 classify；_pick_startup 调用改传 comparison.startup_files
3. _validate_forced_exclusions 并入 _validate_startup_disposition 后删除
4. import 指向全量迁移（工单 5 节，grep 全扫 src tests 零残留）；不 re-export
5. 测试随迁 + 结构测试（工单 6 节）
6. CONTEXT.md 按工单 7 节更新
7. 全量 pytest 绿 + mypy 干净 + 验收全勾后提交（refactor 一条 + docs 一条，风格照仓库）→ PR base 指 main

注意：编辑前先确认 cwd 在 worktree（v4 教训：第一批编辑误落主检出）；勿串行做别的工单。
```

## Comments

（2026-08-09 立项，grilling 共识：候选 3 三轴拆块。Q1 一工单三轴；Q2 命名 categories.py；Q3 启动钩子搬家不升格；Q4 归属裁决清单五项全通过（含 4 节环修正）；Q5 验收加结构测试；Q6 启动验证跟启动走；Q7 classify 接口 + _pick_startup 签名收窄。报告：architecture-review-20260809-102431.html，候选 2（build_manifest_summaries 归 manifest.py）留待下轮。）
