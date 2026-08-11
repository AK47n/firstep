# 01 — 生成侧跨模块同名文件查重兜底（同类冲突提前到生成前报错）

**What to build:** 生成器五道静态门不查**跨模块**同名文件与重复符号——zigbee_uart / zigbee_uart_key 冲突即全部门禁静默通过、UV4 链接期才炸（L6200E）。目标：`resolve_selection` 之后对所选模块的 files 路径集合查重，重复 → 生成前大声失败（400 中文），同类冲突不再等真机编译暴露。

**Status:** resolved（2026-08-11，真机 UV4 复编 0 错 0 警闭环）

## 实施记录（2026-08-11）

- 门禁：generator.py 新增第六道门 `_check_file_path_conflicts(manifests, platform)`——对所选模块（含依赖展开后）的平台条目 files 相对路径集合查重：跨模块同名即报 `DuplicateFilePathError`（400 中文，点名两模块与路径、点明 UV4 L6200E 链接期后果）；同一模块内重复声明同查（parse 侧已防，防内存构造路径）；files 空（实现内嵌母版）跳过；无该平台版本条目跳过（由 `_check_module_files` 报）；只查选中平台条目。门直接吃 manifest 声明不读盘，与既有五道门同处 `generate()`（`_check_module_files` 之后、语料门禁之前）。
- 错误登记：errors.py `error_to_http` 表显式登记 `DuplicateFilePathError` → 400 + 中文文案（GeneratorError 基类已覆盖，按工单 01 ManualReferenceError 先例显式入表 + 注释）；结构防漏登测试自动覆盖。
- 测试（tests/test_generate_collision_gate.py 9 用例 + test_errors.py 1 用例）：
  - 门禁本体内存直喂：跨模块同名拒绝（红证形态）、唯一路径/单选/内嵌空 files/缺平台条目/跨平台同路径均放行、同模块重复声明拒绝。
  - 全链生成红证：`_add_module` 恢复重命名前形态（两模块都声明 code/zigbee_uart.c）→ `generate` 抛 `DuplicateFilePathError`，`error_entry` 映射 400 中文，输出目录不创建。**红证已验**：临时移除门禁调用，该用例即红（生成不再被拦），恢复后复绿。
  - 真实库数据：zigbee 双选 + config 过新门不报（全链生成照常由 test_module_collision.py 双选用例覆盖，同一 generate 接缝）。
- **pytest 1066 全绿**（基线 1056 + 新增 10，无回归）；`mypy src` 干净（32 文件）。
- 不动：selection.py / resolve_selection；库数据（zigbee 已唯一化，不回退）；manifest 形状；符号级查重（不做 C 词法）。
- 遗留：无（真机已闭环）。

## 现状（已核实）

- 出处：zigbee-file-collision 工单观察留痕（2026-08-11，见该工单"观察"节）。
- 五道静态门（generator.py）：_check_module_files / _check_main_calls / _check_module_self_include / _check_unresolved_includes / _check_macro_conflicts——都不查跨模块同名文件路径；符号级查重需轻量 C 词法，收益有限（同类冲突大概率同时撞文件名），本工单只做**文件路径查重**。
- manifest files 是库内单源（平台条目 = 相对路径列表）；库内防回退已有 tests/test_module_collision.py 不变量（全库跨模块重复路径即红）。
- 错误映射：errors.py 单表 + 结构反射防漏登；新增错误类型须登记（未登记 = 500 大声失败）。
- 真机证据：zigbee 双选修复前 UV4 L6200E（链接期），修复后双选 0 错 0 警——查重兜底 = 防御未来库内重蹈（如新补录模块撞既有路径），不与库内不变量测试冲突（那测试管库内数据，本门管生成时组合）。

## 实施

1. generator.py 门禁加一道：所选模块（含依赖展开后）的平台条目 files 相对路径集合查重（跨模块同名即报错；同一模块内 manifest 自身重复同查）；files 空（母版内嵌语义）跳过；只查选中平台条目。
2. 错误类型登记 errors.py → 400 + 中文文案（如"模块 X 与模块 Y 都声明文件 code/zigbee_uart.c"）；结构测试防漏登自动覆盖。
3. 测试：构造双选冲突（fixture 或临时 manifest 模拟重命名前形态）→ 生成 400 中文；zigbee 双选真实数据照常生成（已唯一）；单选照旧；红证 = 恢复冲突形态被拦（参 test_module_collision.py 红证先例）。
4. 位置决策：查重放门禁（生成前），不动 selection.py / resolve_selection；与既有五道门同处。

## 验收

- pytest 全绿 + mypy src 干净。
- 构造冲突工程 → 生成 400 中文报错（不再等 UV4 链接期）；正常双选/单选照旧。
- 结构测试：新错误已登记（未登记即红的既有机制）。

## 真机验收记录（2026-08-11，已闭环）

- 生成：2026C 数字钥匙题双选（`--add zigbee_uart,zigbee_uart_key`，前端同款手动增删语义），产物 `.scratch/real-run/out_2026C_stm32/` 含 `modules/zigbee_uart/` 与 `modules/zigbee_uart_key/` 双模块目录；generate_check 真机内置 UV4 校验 exit=0。
- 编译（UV4 命令行 `-j0 -r` 强制全量重建）：日志 `.scratch/real-run/keil_build_gate.log`——`compiling zigbee_uart.c...`、`compiling zigbee_uart_key.c...` 两行俱在（双选真在工程里），链接 `".\Objects\Project.axf" - 0 Error(s), 0 Warning(s)`，Program Size Code=8292。
- 前置说明：推荐流对"要求表第2项缺失"（题面自注"原题未列出"）先按 clarify 映射答 5 轮未采纳，后经分值自洽推导（评分标准第1项12分+第2项8分=要求表第1项20分）补全题库题面（备份 `.scratch/real-run/topic_2026C_orig.md`）后收敛——属题库数据缺陷修复，与门禁无关。

## 文件边界

`src/contest_generator/generator.py`、`src/contest_generator/errors.py`、`tests/`（新增用例，可建 test_generate_collision_gate.py 或并入既有生成测试）

**明确不动的：** selection.py / resolve_selection；库数据（zigbee 已修复，不回退）；manifest 形状；符号级查重（不做 C 词法）；其他模块。
