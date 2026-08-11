# 01 — 拆 master↔archive 环（扫描/对比模型归 report.py 模型层）

**What to build:** ProjectStructure / ProjectComparison 两个扫描对比模型住在编排器 master.py（:110-146），archive.py:20 被迫模块级 `from .master import ProjectComparison`，master 在 confirm_distillation 内函数级延迟导入 archive（:748）避环——模块 docstring 自述"避开 master ↔ archive 模块级环"。与「判定素材模型归模型层」既定先例（ADR 0001：JudgmentFile/FileVersion 在 report.py，master 构造、llm 消费）相背。本工单把两模型迁 report.py（叶子模型层，只 import 标准库），archive 不再反向依赖 master——环根因切断；master 对 archive 的函数级延迟导入**保留**（C3 链约束：master 模块级拉 archive 会经参考库族破坏 import 链收敛——动机从"避环"澄清为"防链"）。

**Blocked by:** 无

**Status:** resolved（2026-08-09 已合 main PR #34，924 绿 + mypy 干净）

## 需求

1. **report.py 增 ProjectStructure / ProjectComparison**（逐字迁 + docstring；report.py 定位更新 = "蒸馏流程模型层"——判定素材模型 + 扫描对比模型）
2. **master.py**：删两模型定义，改 `from .report import`（master 已 import report：DistillationReport 等，import 行并入既有行）
3. **archive.py:20**：`from .master import ProjectComparison` 改 `from .report import ProjectComparison`（archive 已 import report：DistillationReport / ReferenceCandidate）；模块 docstring 更新（不再"import master"，环已消）
4. **master.py:748 函数级延迟导入保留**，注释更新：动机 = C3 链约束（master 模块级不拉参考库族），非避环
5. **测试**：test_autocommit.py:32 / test_categories.py:27 的 `from contest_generator.master import ProjectComparison, ProjectStructure` 改从 report import（唯一行为面）
6. **结构测试**：两模型定义单址 report.py（grep 式：master/archive 无 class 定义）；archive 无 `from .master import`
7. **CONTEXT.md**：判定模型词条补"扫描/对比模型归模型层（report.py），master↔archive 依赖环消除；master 对 archive 保留函数级延迟导入（链约束非环）"

## 文件边界

- `src/contest_generator/report.py`（+两模型 +docstring 定位）
- `src/contest_generator/master.py`（删定义 + import 改向 + :748 注释更新）
- `src/contest_generator/archive.py`（import 改向 + docstring 更新）
- `tests/test_autocommit.py` / `tests/test_categories.py`（import 行改向，其余零改动）
- 结构测试（test_report 或既有文件）
- `CONTEXT.md`

## 验收

- [ ] 全量测试绿 + mypy 干净
- [ ] 行为零变化——除 import 行外既有用例零改动通过
- [ ] 结构自证：ProjectStructure / ProjectComparison 定义单址 report.py；archive 无 `from .master import`；master 无 class 定义
- [ ] master.py:748 延迟导入保留且注释更新（链约束）
- [ ] CONTEXT.md 更新
- [ ] 独立 worktree + 独立 commit

## Comments

- 2026-08-09 立项（架构评审 2026-08-09 候选 7，用户授权代决）：① 模型迁 report.py（叶子模型层只 import 标准库，无环；判定素材模型归模型层 ADR 0001 先例延续）；② 环根因 = archive 反向依赖 master 的模型，迁走后切断——archive 只剩 report/master_store/参考库族/autocommit/entry_store 依赖；③ **延迟 import 保留**（关键澄清：C3 有两个动机——避环 + 防 import 链；环消后"防链"仍是硬约束：master 模块级 import archive 会经 archive → reference_library/topic_library 拉入参考库族，破坏 C3 "master 不 import 参考库族"收敛——注释从"避环"改"防链"）；④ webapp 不 import 模型（只 import 三个函数）已核实；categories.py:214/225 只是注释提及字段名（不 import）不改；⑤ 行为零变化，收益 = 模型层归位 + 依赖方向澄清 + 未来新消费者（如 archive 之外）可直接依赖 report 模型
- 2026-08-09 实施提示词已交付聊天（文件边界 / 验收 grep / worktree 命令），待新会话执行；已核实 master.py:110-146 为 master 唯二 class（迁后 master 零 class 定义）、webapp.py:61-65 无模型 import、test_autocommit.py:32 + test_categories.py:25-32 为仅有的外部引用
- 2026-08-10 已合 main PR #34（d6ea313），Status 补勾 resolved
