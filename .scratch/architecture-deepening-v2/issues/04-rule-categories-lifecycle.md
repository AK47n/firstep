# 04 — 四大规则类别生命周期参数化（评审候选 4）

**What to build:** 2026-08-06 架构评审报告急需待办第 ② 项：四大规则类别（残留 / 旧 main.c / 基础设施 / 二进制）生命周期参数化。现状：每个类别的识别与处置逻辑散布 master.py 六处——扫描分类（4 个平行 if 分支）、对比并集（4 行）、越界拦截（4 个平行 raise）、报告汇编（4 段循环）、覆盖校验扣除、disposition 校验（4 个校验函数）；第四份拷贝（二进制，判例 08）两天前刚加，加类别 = 复制六处逻辑，必然再漏。

**改法（评审建议）：** 每类一条 `RuleCategory` 描述（识别规则 + 确定性处置 + 报错文案），流水线遍历 `RULE_CATEGORIES` 表，新增类别 = 加一条描述 + 结构/对比字段声明。

**Status:** resolved

## Answer

- [x] `RuleCategory`（master.py）：key（结构/对比字段名）/ name（报错文案用）/ reason_of（扫描识别，统一 (rel, path) → 原因，二进制用 `_binary_reason` 包内容探针）/ report_reason（报告汇编取原因：按路径重算或常量，此时无文件内容可读）/ disposition（keep / exclude）/ out_of_scope_message（越界拦截文案）/ disposition_message（处置校验文案）
- [x] `RULE_CATEGORIES` 四条描述；顺序即扫描判定顺序（先便宜的后读文件的：残留 → main.c → 基础设施 → 二进制，互斥先到先得，for-else 等价原 continue 语义）
- [x] 六处全部改为遍历类别表：扫描分类（category_lists 按 key 分桶）、对比并集（字典推导）、越界拦截、报告汇编（keep 类别在前 / exclude 在后，与旧行为逐位一致）、覆盖校验扣除（category_paths 并集）、disposition 校验（`_validate_category_disposition` 一个函数替代四个）
- [x] `_source_project` 的 keep 类别取源兜底（原只写死 infrastructure）改为遍历 keep 类别
- [x] 文案契约保持：测试断言的"无需 AI 判定"、"{类别}必须剔除/保留"逐字不变（含"旧工程 main.c 必须剔除"的空格——属性推导会丢空格，改用显式字段）
- [x] 防漂移测试 `test_rule_categories_keys_match_structure_fields`：类别 key 必须与 ProjectStructure / ProjectComparison 字段一一对应
- [x] 全量 404 pytest 绿（403 基线 + 1 新测试）+ mypy 17 文件干净；CONTEXT.md 词表补"文件类别"、架构要点补"文件类别生命周期单源化"
