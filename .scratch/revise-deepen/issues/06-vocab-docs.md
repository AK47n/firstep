# 06 — 词表与文档：CONTEXT.md 术语 + 必要 ADR + CHANGELOG

**要做什么：** 「修订」（revision：新 Q&A → 一致性检查 → 覆盖式重生成）、「深化」（deepening：按功能需求填 TODO → 编译验证闭环）、「上下文清单」（生成尾部落盘的纯新增隐藏文件，历史目录修订的直读来源）三个术语进 CONTEXT.md 词表；修订与深化的关键架构决策（两段式 API、覆盖式重生成 + 备份回滚、main.c 保全策略、深化编译验证硬门槛）如有必要落一条 ADR；CHANGELOG 由提交信息自动补录（中文）。

**被谁阻塞：** 05（功能落地后文档与实现一致）

**状态：** resolved（2026-08-21 实施完成）

## Comments

**实施记录（2026-08-21）：**
- CONTEXT.md 词表加三条：「修订」（revision：影响分析 → 确定性 diff → 覆盖式
  重生成 + 备份回滚）、「深化」（deepening：填 TODO → 编译验证闭环）、
  「上下文清单」（.contest_context.json：生成输入落盘 + 历史目录反推），各
  指向主要实现（impact.py / revision.py / deepen.py / context_manifest.py /
  webapp 端点）。
- ADR 0014 落盘：两段式 API / 确定性 diff（依赖展开集判定）/ 覆盖式重生成 +
  备份回滚 / main.c 保全策略 / 深化编译验证硬门槛 / 上下文清单六个关键决策 +
  「考虑过的方案」对照。
- CHANGELOG 中文条目由各提交信息自动补录（01-06 全部提交信息中文）。
- tests/test_repo_language.py 3 passed（语言规范兜底绿）。

- [x] CONTEXT.md 词表含「修订」「深化」「上下文清单」三条，指向主要实现
- [x] 必要 ADR 已写（若 01-04 实现中浮现出值得留痕的决策）
- [x] CHANGELOG 中文条目就位
- [x] 语言规范检查通过（tests/test_repo_language.py 绿）


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
