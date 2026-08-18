# 01 — 收敛提速：核验轮短标记提前停 + 轮数上限可配置

**要做什么：** 推荐收敛循环第 2 轮起每轮都要求模型全量输出功能需求层（2-4 min/轮、上限 4 轮）。本工单两件事：①核验轮模型自报"无修订"时输出短标记 `{"converged": true}`（秒级响应），驱动层用上一轮结果提前收敛；②收敛轮数上限可配置（设置页 2/3/4，缺省 4）。

**被谁阻塞：** 无（在 recommend-speedup/01 的核验式修订基础上深化）

**状态：** resolved

- [x] ModuleSelection 增 `converged` 字段；`llm.select_modules` 解析 `{"converged": true}` 短标记（严格 true 才算，false/缺字段照常走域判决；短标记跳过 build_module_selection）。
- [x] `_revision_prompt` 核验轮指令改为「无修订 → 输出短标记；有修订 → 输出完整新层」。
- [x] 收敛循环：round > 1 且 selection.converged → 发 converged 事件、用上一轮结果提前停；第 1 轮出现 converged 当空结果忽略（照常比较）。
- [x] `run_recommendation(max_rounds=...)` 透传；AppConfig `recommend_max_rounds`（2-4，缺省 4）+ 设置页下拉 + settings GET/PUT。
- [x] 测试：短标记提前停（calls=2 且返回上一轮结果）、轮 1 短标记忽略、max_rounds=2 生效、llm 解析层短标记/严格 true、webapp 轮数上限接线（默认 4 / 配置 2 / 越界 400）。

## Notes

- 语义等价性：模型自报"无修订" = 两轮输出相同，与既有"两轮 key 一致"是同一信任模型；短标记还省掉核验轮的全量输出（2-4 min → 秒级）。
- 驱动层兜底保留：模型有修订时照旧输出完整层、照旧 key 比较；converged 只是"自报一致"的快路径。
- 与推荐缓存（llm-cost-control/02）正交：缓存管"同题跨运行复用"，短标记管"单次运行内收敛提速"。
- 验证：pytest 全绿、`node --test tests/js/` 全绿、`mypy src` 干净。
