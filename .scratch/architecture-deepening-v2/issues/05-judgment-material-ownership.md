# 05 — 判定素材模型归属（评审候选 5，依赖倒置）

**What to build:** 2026-08-06 架构评审报告急需待办第 ③ 项：判定素材模型归属。现状问题：
1. master.py:48 从 llm.py 导入 `FileVersion / JudgmentFile / LLM`——纯逻辑核心（master）反向依赖 AI 层（llm）的模型类型（依赖倒置反了：判定素材是 master 构造、llm 消费的，模型应归模型层，llm 依赖模型层而非反向）。
2. 版本分组不变量（内容一致的工程合并一个版本、组间不重不漏）四处各写一遍：build_judgment_files 构造、parse_summary_report 词表提取、_split_merged_versions 并集提取、_judgment_batches 拆批依赖。

**改法：** 判定素材模型（JudgmentFile / FileVersion）迁到 report.py（判定模型 = 输入素材 + 输出条目，与 arch-v2 把 FileDecision 收进 report.py 同一模式）；版本分组在模型上唯一声明（version_groups 属性）与校验（__post_init__）。

**Status:** resolved

## Answer

- [x] report.py 加 JudgmentFile / FileVersion（判定素材，frozen dataclass）：`version_groups` 属性 = 版本分组提取唯一出处；`__post_init__` 校验不变量（版本非空 / 各组非空 / 组间工程名不重叠，违者 ReportError）
- [x] llm.py 删本地定义，改从 .report 导入 JudgmentFile；parse_summary_report 词表与 _split_merged_versions 并集改用 `file.version_groups`
- [x] master.py:48 只剩 LLM 协议（AI 接缝参数类型，实现与解析留在 llm 层——协议归实现层是刻意保留，见下）；模型类型改从 .report 导入；**无循环导入**（llm → report / master → llm + report，单向链）
- [x] 消费方导入面更新：tests/fakes.py、test_llm.py、test_webapp.py 的 JudgmentFile / FileVersion 改从 .report 导入
- [x] 新测试 tests/test_report.py（判定素材模型不变量 4 条：分组提取 / 空版本拒绝 / 空组拒绝 / 重叠组拒绝）
- [x] 全量 407 pytest 绿（403 + 4）+ mypy 17 文件干净；CONTEXT.md 词表"报告模型"改"判定模型"（含素材与不变量）、架构要点补"判定素材模型归模型层（依赖倒置）"

**刻意保留（评审未点名，文档化决策）：** LLM 协议留在 llm.py——它是 AI 层的接缝（协议 + 实现 + 解析同层内聚），master 仅作参数类型引用、不依赖具体实现；VersionSummary / FileSummary（摘要产物模型）留在 llm.py——llm 内部两阶段流程专用，不跨层。版本分组**构造**（按内容哈希分组）仍在 build_judgment_files——那是生产者唯一逻辑，四处手抄的是分组**提取**，已单源化。
