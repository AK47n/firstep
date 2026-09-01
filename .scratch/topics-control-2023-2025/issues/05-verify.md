# 05 — 全库验收（拆条完整性 + 分类全量 + 前端冒烟）

**要做什么：** 本特征整体验收（20 条 = 15 老 + 5 新）：

1. **后端断言**（pytest / 脚本）：
   - 全部 20 条 `category` ∈ ("control", "other") 且**非空**（补标完成态）；
   - 5 道新题（2023E/G/I、2025E/H）topic.md 含「一、任务」「二、要求」「三、说明」「四、评分标准」（按题实际结构）与 `# <题名>（X 题）`；manifest 字段齐全（year/number/problem_md/original_pdf/programs/category）；`original_pdf` 存在且 < 1MB；`resolve_number` 可解析；
   - 新题 `original_pdf` 均指向小题 PDF（非 34MB 汇编副本——按文件名/大小判据）；
   - 图注：题面引用「图 N」的条目已含 `[图N 标注` / `[示意图`（enrich 幂等结果）或题面无图引用（合法）。
2. **前端冒烟**（CDP）：题库 tab → 筛选「控制题」→ 列表出现 2023E/G/I/2025E/H 且无 2026A 等 other 题 → 打开 2023E 详情（题面全文 + 原 PDF 页面 + 图注段）→ 编辑表单分类下拉（control/other）→ 保存后 category 透出。
3. **回归**：pytest 全绿 + js 全绿 + 仓库语言检查（tests/test_repo_language.py）通过。

**被谁阻塞：** 02 / 03 / 04（验收对象为补标与拆条完成态）。

**状态：** ready-for-agent

**验收：** 全部 ✓（上述三项清单全过，验收记录写在工单尾部；发现缺口回填对应工单并复验）。

- [ ] 后端断言脚本/测试（20 条 category 非空合法 + 5 新题结构/manifest/PDF/图注）
- [ ] CDP 冒烟：筛选 → 列表 → 2023E 详情 → 编辑表单 → 保存
- [ ] 回归：pytest + js + 语言检查全绿
- [ ] 验收记录（含任何回填与复验）

**参考：** spec 六（测试决策）。
