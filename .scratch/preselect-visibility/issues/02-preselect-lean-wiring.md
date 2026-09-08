# 02 — 预筛装配点改用瘦身行（截断消失、关键模块可见）

**要做什么：** 让推荐链路的提示词真正吃到瘦身行：装配点（网页与 CLI 两条入口）把平台全量摘要替换为瘦身行再交给预筛，于是全库装得进预算、`truncated` 恒为 False、「按题面初筛 N/M」注记不再出现，`tests/test_preselect_coverage.py` 的 6 条 xfail 全部 XPASS——摘掉标记后它们成为常规守卫（库再长大到装不下就红）。下游四条消费链（提示词 / 库指纹 / 设计报告草稿 / 修订影响分析）因为取同一份装配结果而自动一致。

**被谁阻塞：** 01 — 摘要行瘦身形态（manifest 层）。

**状态：** resolved

- [x] 装配点改为瘦身行取源（网页 `webapp` 装配点在预筛前把 `topic.manifest_summaries` 换成 `lean_copy()` 形态；CLI 路径无预筛、清单行照旧完整——两条入口的行形态由同一 `to_line()` 出口决定，不存在两套渲染）
- [x] 真实库跑预筛：`truncated` 为 False、`len(summaries) == total`（6 组题面全部 86/86、84/84）；小预算直造截断用例继续绿
- [x] `tests/test_preselect_coverage.py` 6 条 xfail 标记摘掉转常规守卫；`test_preselect_subset_is_contained_in_full_library` 的「截断必须发生」断言改为「全库可见」不变量（另立 `test_preselect_whole_library_visible_for_real_topics`）
- [x] `tests/test_llm.py::test_recommend_real_library_budget` 按瘦身形态复测通过（最坏形态仍 ≤ 网关预算 −2KB）
- [x] 端点级用例 `test_recommend_route_shows_lean_summary_lines_for_whole_library`：模型实际收到的清单行无套件段/采购链接、依赖段保留、全库条数齐全
- [x] `python -m pytest -q` 全绿：3876 passed, 2 xfailed（余下 2 条 = 骨架映射，工单 03/04）

## 答复（code-review 双轴整改，2026-09-08）

- **Spec 轴**：`lean_line` 标志进 `__eq__` 使「清单行 == 判据全集」的短路在网页路径恒不成立（`known_summaries` 恒传、同一份库重复进收敛循环）→ 新增 `selection._same_summary_content`（只比库内事实字段、不比行形态）+ 红证用例 `test_run_recommendation_omits_known_when_only_render_mode_differs`。
- **Spec 轴（验收口径变更）**：`2021F/stm32` 的必需项 `xunji` 在库内只有 mspm0 条目，是 xfail 期间被掩盖的不可能断言；按事实改为 `("motor", "pid", "key", "oled")`，并在用例注释与本答复里留痕（不是为了让测试变绿而放宽判据——修好后其余 5 组一次通过）。
- **探针同步**：`.scratch/library-audit/probe_guard_cases.py` 改为走瘦身行形态（与生产同源），否则复测结论与生产相反。
- **记账口径**：`budget.py` 摘要段数字改用生产实现实测值（28071B / 28062B），不再引用探针自算值。
