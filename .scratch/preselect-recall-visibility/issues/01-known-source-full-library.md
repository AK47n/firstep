# 01 — 判据取源归位：库内合法性用平台全量，清单行仍用预筛子集

**要做什么：** 模型推荐库内模块（哪怕它没在提示词清单里）时，推荐流程不再报「库中不存在模块」而中断；推荐结果里这些模块能正常配默认实例。展示给模型的清单行保持现状（仍是预筛子集，不改可见性）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `PreselectResult` 同时给出「子集」与「平台全量」两份摘要（外加既有总数 / 是否截断），预筛是这两份的唯一出处。
- [x] `TopicContext` 同时携带「喂模型的清单行」与「判据用的平台全量」两份摘要；网页推荐路由的预筛替换只作用于清单行字段，判据字段不受影响。
- [x] 收敛循环与推荐编排把「平台全量」用于：模型推荐合法性校验、多实例能力清单、默认实例兜底；提示词清单段仍只渲染子集。
- [x] `select_modules` / `select_modules_convergent` 的「合法性全集」为可选入参；全量 == 清单行时不传，行为与现状逐字节一致（既有调用与测试零改动）。
- [x] 真实库实测：在 2024H/stm32 这类子集不含 `motor` 的题面上，模型推荐 `motor` 不再抛错，推荐结果照常以 done 收尾。
- [x] 真幻觉仍被拒：推荐库内确实没有的 slug，仍是 400 中文错误、文案逐字不变。
- [x] 推荐 `led`（多实例、且在子集外）时 done 载荷带 `led` 的平台默认实例清单，实例卡有值。
- [x] 既有测试全绿（`pytest`），含 CLI 对偶路径。

## Comments

**改动面**：`selection.py`（`PreselectResult.library_summaries` 字段 + `select_modules_convergent` 的 `known_summaries` 可选入参 + `run_recommendation` 从 `topic.library_summaries` 取判据）、`llm.py`（`LLM` Protocol + `DeepSeekLLM.select_modules` + 路由包装类三处签名；`known_slugs` 与 `multi_instance_slugs` 改取 `known_summaries or manifest_summaries`）、`generator.py`（`TopicContext.library_summaries` 字段 + 两个装配点同源填充；顺带删掉一处重复的平台过滤）、`webapp.py`（预筛只改清单行、判据字段不动；库指纹取源改全量）。测试侧：`tests/fakes.py` 与 4 个测试文件的假 LLM 补收尾 `**_unused` / `**kwargs`（协议新增可选入参，不影响既有断言）。

**红证（先红后绿，两处）**：

1. 解析层（真域判决，逐字）：`tests/test_llm.py::test_select_modules_accepts_module_outside_shown_list_but_in_library` 只传子集时失败，报错逐字为

```
contest_generator.selection.SelectionError: 模型推荐了库中不存在的模块：motor
→ contest_generator.llm.LLMError: 模块选择连续 1 次调用失败：模型推荐了库中不存在的模块：motor
```

传 `known_summaries=full` 后转绿，`result.modules == ("motor",)`，且提示词正文里不含 `motor`（清单行仍只渲染子集）。

2. 端点（最高 seam）：`tests/test_webapp.py::test_recommend_route_passes_full_library_as_known` 把假库撑过 `MODULE_SUMMARY_BYTES` 使预筛真截断，假 LLM 按生产语义用 `known_summaries` 做域判决——把 `known` 临时退回清单行后该用例失败（`清单行未被截断（26 条）`，随后域判决拒绝 dht11、推荐流中断），恢复后绿。

**接缝更正（过程留痕）**：最初把红证写在假 LLM 的编排测试里，跑出来「去掉修复也绿」——假 LLM 不经过 `build_module_selection` 域判决。红证因此落在 `select_modules` 解析层（唯一能跑真域判决的层）；端点用例改为「假 LLM 按生产语义用 `known_summaries` 判域」，从而端到端覆盖「路由把全集传下去 → 推荐不被拒 → done 载荷带出模块」。

**验收证据**：
- 端点 seam：`tests/test_webapp.py::test_recommend_route_passes_full_library_as_known`（子集 26 条 ⊂ 全量 124 条，done 载荷含推荐模块）。
- 解析层判据：`tests/test_llm.py::test_select_modules_accepts_module_outside_shown_list_but_in_library`、`::test_select_modules_rejects_hallucinated_module_even_with_library`（真幻觉仍 `ERROR_KIND_CLIENT`，文案含「库中不存在的模块：motor」）。
- 编排层：`tests/test_selection.py::test_run_recommendation_passes_library_summaries_as_known`（全集进判据、清单行仍是子集）、`::test_run_recommendation_default_instances_use_library_summaries`（子集外的 `led` 也兜底红黄绿）、`::test_run_recommendation_without_library_summaries_keeps_old_behaviour`（不传 = 旧行为）。
- 全量：`python -m pytest -q` → **3852 passed, 6 xfailed**；`mypy` 三个改动源文件零告警（`webapp.py` 的 8 条告警经 `git stash` 对照确认为既有基线）。

**code-review 整改（双轴，2026-09-08）**：
- Standards 硬违规 1（测试绕开最高 seam、自建路由装配）→ 已改为 `/api/recommend` 端点用例，删除 `_real_topic_context` / `_run_recommend_with_preselect`。
- Standards 硬违规 2（重复 `_drain`）→ 已删除重复定义。
- Standards 判断项：`PreselectResult.full` → `library_summaries`（命名自解释、与 `TopicContext` 同词）；删掉 `run_recommendation` 的 `library_summaries` 形参（判据从 `topic` 取，去掉三级回落）；`generator.py` 重复平台过滤已删。
- Spec 轴：done 载荷含子集外模块的断言改由端点用例承担（假 LLM 按生产语义判域）；「CLI 与既有测试零改动」经「全量 == 清单行时不传」整改成立；缓存指纹取源改全量（见 spec「实现决策·缓存」）。

**未做（留给后续批次）**：可见性本身未改（2024H 仍只见 34/86），预筛评分 / 匹配粒度 / 摘要行瘦身归下一批。
