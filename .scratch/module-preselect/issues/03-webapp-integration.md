# 03 — webapp 推荐路由接入预筛（指纹口径 + 提示词标注）

**要做什么：** 让真实 `/api/recommend` 请求使用预筛后的摘要子集——mspm0 线现实形态（带参考全文 / 澄清历史）不再超 128KB 网关预算；缓存指纹与模型实际所见一致；提示词明说「按题面初筛 N/M」。

**被谁阻塞：** 01（纯函数）、02（预算常量与回归测试先行校准）。

**状态：** resolved

**实施记录：** webapp `/api/recommend` 路由在装配 topic 后、指纹计算前接入 `preselect_module_summaries`（题面 = topic.problem_text，词表 = DEFAULT_WORDLIST，预算 = MODULE_SUMMARY_BYTES）；发生子集化时 `dataclasses.replace` 替换 `topic.manifest_summaries` + 注记文案「（按题面初筛 N/M 条，仅展示前 X wire 字节）」，未子集化 = topic 零变化 + 空注记。指纹改用预筛后列表（模型实际所见）。注记穿透链：run_recommendation → select_modules_convergent（optional_kwargs 条件传）→ llm.select_modules（协议抽象 / DeepSeekLLM / RemoteLLM 三处签名 + FakeLLM / RecordingLLM / _RecordingConvergenceLLM 同步）→ `_selection_user_prompt`（标题行拼接，空串逐字节不变）。全链路验证 `test_recommend_preselect_fits_keeps_full_catalog_and_no_note`（webapp 集成，FakeLLM 记录 select_calls）+ `test_convergent_passes_preselect_note_every_round`（非空每轮透传）+ `test_selection_prompt_preselect_note_two_states`（注记两态）。2026 真题覆盖探测：8/8 题命中集充分、批次 13 新件按题面进入子集、常备件基本全在（.scratch/recommend-covered-check/probe_2026_preselect.py）。mypy 零新增（webapp 8 错存量实锤：stash 对比原文件同数）。全量 pytest 最终结果见下。

- [x] `/api/recommend` 路由在 `_assemble_topic_context` 之后、`library_fingerprint` 之前应用预筛（`preselect_module_summaries`，题面 = topic.problem_text，词表 = 默认词表，预算 = `MODULE_SUMMARY_BYTES`）；预筛结果替换 `topic.manifest_summaries`（`_default_instances_for` 同源受益，命中模块必在子集内）
- [x] `library_fingerprint` 改用预筛后摘要列表（模型实际所见）；同题面同预筛 = 同指纹，缓存语义不变
- [x] `_selection_user_prompt` 标题行携带预筛注记（「模块库可用模块（按题面初筛 N/M，仅展示前 X wire 字节）：」）；未预筛 / 全量未截断时标题逐字节不变（向后兼容）
- [x] webapp 集成测试：真实库下 `/api/recommend` 载荷 ≤ MAX_REQUEST_BYTES 且带预筛注记；stm32 线注记不出现（全量送达）
- [x] `test_llm.py` 注记两态测试：预筛形态出现注记、未预筛形态标题逐字节不变
- [x] CLI 验收脚本路径核对（generate_check 走 HTTP，自动对偶，零改动）并验证
- [x] 全量 pytest + node 测试无回归

- [ ] `/api/recommend` 路由在 `_assemble_topic_context` 之后、`library_fingerprint` 之前应用预筛（`preselect_module_summaries`，题面 = topic.problem_text，词表 = 默认词表，预算 = `MODULE_SUMMARY_BYTES`）；预筛结果替换 `topic.manifest_summaries`（`_default_instances_for` 同源受益，命中模块必在子集内）
- [ ] `library_fingerprint` 改用预筛后摘要列表（模型实际所见）；同题面同预筛 = 同指纹，缓存语义不变
- [ ] `_selection_user_prompt` 标题行携带预筛注记（「模块库可用模块（按题面初筛 N/M，仅展示前 X wire 字节）：」）；未预筛 / 全量未截断时标题逐字节不变（向后兼容）
- [ ] webapp 集成测试：真实库下 `/api/recommend` 载荷 ≤ MAX_REQUEST_BYTES 且带预筛注记；stm32 线注记不出现（全量送达）
- [ ] `test_llm.py` 注记两态测试：预筛形态出现注记、未预筛形态标题逐字节不变
- [ ] CLI 验收脚本路径核对（generate_check 走 HTTP，自动对偶，零改动）并验证
- [ ] 全量 pytest + node 测试无回归
