# 01 — generate_check 与门禁同源（验收脚本不再抄门禁逻辑）

**What to build:** 真机验收脚本 `.scratch/real-run/generate_check.py` 的 `check_artifacts` 把生成侧门禁逻辑重实现了一遍（FENCE_RE 抄 `clex.fence_line_indices`、`_INCLUDE_RE`/`_resolves` 抄 `clex.extract_quoted_includes` + `_check_unresolved_includes`、`EXTERNAL_HEADERS` 手维护 `_LIBC_HEADERS` + keil/ccs 外部头镜像含 mspm0 前缀豁免）——门禁一改脚本静默漂移，真机验收给假信心；契约测试只查 SSE 词表与 payload 字段集，不查对偶。目标：check_artifacts 的"门禁类"检查改为对**产物树重建语料**跑真正的 `run_generation_gates`（工单 generation-gate-registry/01 产物：表 + runner 可 import），镜像删除，验收测的就是生产逻辑本身。

**Status:** implemented（2026-08-11，真机 2021F 全流程 UV4 0 错 0 警闭环）

## 实施记录（2026-08-11）

- 产物树语料构建：generator.py 新增 `build_output_tree_corpus(output_dir, platform, search_dirs) -> ModuleCorpus`（build_module_corpus 后）——从生成产物树重建语料：modules = `output_dir/modules/<slug>/` 下文件（iter_project_files 同规噪音跳过、按 slug 排序，kind 判定与 build_module_corpus 同规，own_dir = 文件所在目录）；modules 目录不存在 = 空；master_headers = 产物树 *.h 排除 modules/ 子树；main_c 读盘（OSError 容错取空）；missing_platforms / missing_files = 空（生成成功 = 文件俱在）；master_search_dirs = 调用方传入。纯函数，tmp_path 直构可测；唯一 src 改动。
- 换闸：generate_check.py 门禁镜像段（`FENCE_RE` / `_INCLUDE_RE` / `EXTERNAL_HEADERS` / `_resolves` / `is_external_header` 及逐字重实现的围栏 + include 解析 + 豁免集扫描）删除；check_artifacts 改为 `build_output_tree_corpus(out_dir, platform, search_dirs)` → `run_generation_gates(corpus, [], platform)`（manifests 传空 = file_path_conflicts 空表直过，注释说明：产物树无 manifest 声明可查，跨模块同名由库内不变量 + 生成前门禁管）；GeneratorError 按既有失败汇报形状输出（门禁消息是现成中文）。补丁器验证段（读补丁后 .uvprojx/.cproject 的 IncludePath → 搜索目录，patch 没写进模块目录 → include 解析门在此失败）与 uv4_build 不动；package import 经 `sys.path.insert(0, <repo>/src)` 引入。
- 测试（tests/test_generator.py 5 用例 + test_generate_check_contract.py 2 结构钉）：
  - 构建器：tmp_path 直构产物树断言形状（modules 按 slug 排序 / rel 相对模块目录 / kind / own_dir / master_headers 排除 modules/ / main_c 读盘 / master_search_dirs 透传）；无 modules 目录 = 空。
  - 门禁对偶：产物树含未解析 include → `run_generation_gates(build_output_tree_corpus(...), [], platform)` 抛 UnresolvedIncludeError；产物树模块头重定义母版接口宏 → MacroRedefinitionError；干净产物树六道全过——证明产物树路径跑的是真门禁。
  - 结构钉：generate_check.py AST 级断言镜像符号（FENCE_RE / _INCLUDE_RE / EXTERNAL_HEADERS / _resolves / is_external_header）零定义（注释提及不算），且从 contest_generator.generator 引入 build_output_tree_corpus + run_generation_gates——镜像复活即红。
- **pytest 1075 全绿**（基线 1068 + 新增 7，无回归）；`mypy src` 干净（32 文件）。
- CONTEXT.md 校验语料词条补"产物树侧可重建（build_output_tree_corpus，真机验收脚本与门禁同源跑同一套谓词）"，出处列补 build_output_tree_corpus。
- 不动：门禁谓词与表 / errors.py / keil.py / ccs.py / patchers.py / webapp.py / selection.py / uv4_build。

## 真机验收记录（2026-08-11，已闭环）

- 起服务 8000（`PYTHONPATH=src python -m contest_generator.webapp`），curl 探活 200。
- 跑 2021F 真实赛题全流程（`python generate_check.py 2021F --clarify clarify_2021F.json`）：DeepSeek 推荐 4 轮 done（digit_uart / motor / pid / led_beep + 依赖拉入 ball_detect / ml_mpu6050）→ 骨架 → 生成 53 文件 → **产物检查 = 产物树重建语料跑真门禁全过（"门禁全过（产物树语料重建，与生成同源）"）** → UV4 命令行构建 **0 Error(s), 0 Warning(s)**（`\.\Objects\Project.axf" - 0 Error(s), 0 Warning(s).`，日志 .scratch/real-run/keil_build.log）——结果与改造前一致。
- 前置说明：2026C 双选路径本次遇 LLM 变异性（收敛循环不携带澄清历史，模型对题面补录说明换措辞反复补问"序号2缺失"——题库数据修复与澄清机制之外，与门禁/本工单无关；补记 clarify_2026C.json +1 条新措辞映射），验收改走 2021F（本工单验收原列举的备选）。

## 验收

- [x] pytest 全绿（1068 基线 + 新增 7 = 1075，无回归）+ `mypy src` 干净。
- [x] 产物树门禁对偶用例证明：未解析 include / 宏冲突在产物树上被真门禁拦下（UnresolvedIncludeError / MacroRedefinitionError）。
- [x] 结构钉：generate_check.py 门禁镜像清零（FENCE_RE/_INCLUDE_RE/EXTERNAL_HEADERS 不复活，AST 断言）。
- [x] 真机：起服务（8000）→ generate_check 实跑 2021F → 全部检查过（产物门禁全过 + UV4 0 错 0 警），与改造前一致——验收脚本现在与生产同源。
- [x] 工单补实施记录 + 验收勾选，Status implemented。

## 现状（已核实，2026-08-11 架构评审）

- 门禁表（generator.py，PR #48 合入）：`GENERATION_GATES` 六条 + `run_generation_gates(corpus, manifests, platform)`；五道吃 `ModuleCorpus` 的谓词是纯函数（main_calls 含围栏检测 / self_include / unresolved_includes / macro_conflicts / module_files），`_check_file_path_conflicts` 吃 manifests+platform。
- `ModuleCorpus`（generator.py:433）：modules（slug → ModuleFile 列表，含 rel/kind/text/own_dir）/ missing_platforms / missing_files / master_headers（相对路径+文本）/ master_search_dirs / master_project_dir / main_c——**全部字段可从产物树重建**（生成成功 = 文件俱在，missing 两组取空）。
- generate_check.py 现状（行号以实施时读盘为准，探索报告）：FENCE_RE(38) / EXTERNAL_HEADERS(40-48) / _INCLUDE_RE+_resolves(49, 95-96) / check_artifacts(52-92) 是门禁镜像；uv4_build(160-180) 是唯一真权威检查（UV4 命令行编译），**不动**；另有一段"产物检查读 .cproject includePath（CCS 语义，模块路径应在 ${PROJECT_LOC}/modules/<slug>/code）+ mspm0 豁免 ti_msp_dl_* 器件头"（2f0d5ba 记录）——这是**补丁器验证**（验证 patcher 干对了活），不是门禁镜像，**保留**。实施时先读文件把"门禁镜像"与"补丁器验证"两段分开，只换前者。
- 豁免集真实出处：`_LIBC_HEADERS`（generator.py:115）+ `patchers.external_headers(platform)`（keil/ccs 各声明、含 mspm0 ti_msp_dl_* 前缀）——门禁内部已有，镜像删除后自然同源。
- 契约测试 tests/test_generate_check_contract.py 只查 SSE 词表（206-215）与 payload 字段集（55-86），无门禁对偶守卫。

## 实施

1. **generator.py 加产物树语料构建**（唯一 src 改动）：
   - `build_output_tree_corpus(output_dir: Path, platform: str, search_dirs: Sequence[Path]) -> ModuleCorpus`：从生成产物树重建语料——modules = `output_dir/modules/<slug>/` 下的文件（rglob，kind 判定与 build_module_corpus 同规），modules 目录不存在 = 空；master_headers = `output_dir` rglob `*.h` **排除 modules/ 子树**；master_project_dir = output_dir；main_c = `output_dir/main.c` 读盘；missing_platforms / missing_files = 空（生成成功即文件俱在）；master_search_dirs = 调用方传入（generate_check 已会读 .uvprojx/.cproject 的 IncludePath）。
   - 纯函数，tmp_path 直构产物树可测。
2. **generate_check.py 换闸**：
   - check_artifacts 内"门禁镜像"段（围栏 / include 解析 / 豁免集）删除，改为：`corpus = build_output_tree_corpus(output_dir, platform, search_dirs)` → `run_generation_gates(corpus, [], platform)`（manifests 传空 = file_path_conflicts 空表直过，注释说明：产物树无 manifest 声明可查，跨模块同名由库内不变量 + 生成前门禁管）；捕获 GeneratorError 按既有失败汇报形状输出（门禁消息是现成中文）。
   - "补丁器验证"段（.cproject/.uvprojx IncludePath 含模块目录等）保留不动；uv4_build 不动。
   - 从 package import（generate_check 是本仓库工具，package 可用；如现状为全自包含脚本，引入 package 依赖即本工单意图）。
3. **测试**：
   - tests/test_generator.py（或新 test 文件）：build_output_tree_corpus 用例——tmp_path 直构产物树（modules 含 c/h、母版头、main.c、搜索目录），断言 modules 形状 / master_headers 排除 modules/ / main_c 读盘 / 无 modules 目录 = 空；**门禁对偶用例**：直构含未解析 include 的产物树 → `run_generation_gates(build_output_tree_corpus(...), [], platform)` 抛 UnresolvedIncludeError；含宏冲突产物树 → MacroRedefinitionError（证明产物树路径跑的是真门禁）。
   - tests/test_generate_check_contract.py：加结构钉——generate_check.py 源码不再含 FENCE_RE / _INCLUDE_RE / EXTERNAL_HEADERS 镜像定义（AST 或源码断言），且含 run_generation_gates / build_output_tree_corpus 调用（防回退：镜像复活即红）。
4. **CONTEXT.md**：校验语料词条补一句——"产物树侧可重建（build_output_tree_corpus，真机验收脚本与门禁同源跑同一套谓词）"。

## 文件边界

- src/contest_generator/generator.py —— 唯一 src 改动（+build_output_tree_corpus）
- .scratch/real-run/generate_check.py —— check_artifacts 门禁镜像段换闸，删 FENCE_RE/_INCLUDE_RE/EXTERNAL_HEADERS；补丁器验证段与 uv4_build 不动
- tests/test_generator.py（或新文件）+ tests/test_generate_check_contract.py —— 构建器/对偶用例 + 结构钉
- CONTEXT.md —— 词条一句
- **不动**：门禁谓词与表、errors.py、keil.py / ccs.py / patchers.py、webapp.py、uv4_build

## 验收

- pytest 全绿（1068 基线 + 新增，无回归）+ `mypy src` 干净。
- 产物树门禁对偶用例证明：未解析 include / 宏冲突在产物树上被真门禁拦下。
- 结构钉：generate_check.py 门禁镜像清零（FENCE_RE/_INCLUDE_RE/EXTERNAL_HEADERS 不复活）。
- 真机：起服务（8001）→ generate_check 实跑一张真实赛题（如 2026C 双选或 2021F）→ 全部检查过（含 uv4_build 0 错 0 警），结果与改造前一致——验收脚本现在与生产同源。
- 工单补实施记录 + 验收勾选，Status implemented。
