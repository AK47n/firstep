# 01 — 摘要行瘦身形态（manifest 层）

**要做什么：** 给模块摘要对象加一种「瘦身行」渲染形态：`- <slug>: <有界首句>（依赖: …）（多实例：…）（副产物模板可选：…）（互斥组：…）`。有界首句按「。」「；」切第一句、再按 100 字符硬上限截断；套件段与采购链接不进瘦身行。做完后**真实库全库（stm32 86 条 / mspm0 84 条）用瘦身行的 wire 总量装进 `MODULE_SUMMARY_BYTES=40000`**，这是下一张工单让「截断消失」的前提。既有 `to_line()` 完整行语义不变。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

- [ ] `ManifestSummary` 新增瘦身行渲染（唯一实现，字符串只在 prompt 边界渲染一次；不在测试里复制行文法）
- [ ] 有界首句：只在「。」「；」切分（不切「，」「：」——`motor` 的能力句必须留住），再按 100 字符上限截断
- [ ] 瘦身行保留决策信息：依赖段、多实例段（上限 + 变体）、副产物模板段、互斥组段；**不含**套件段与采购链接
- [ ] 行渲染测试进 `tests/test_manifest.py`：断言瘦身行含/不含哪些段、首句切分与截断边界（含 `motor` 首句不被「：」切碎的负例）
- [ ] 全库字节账测试：真实库（`library/modules`）两平台全量瘦身行 wire 总量 ≤ `MODULE_SUMMARY_BYTES`，并断言余量 ≥ 5KB（库长大到临界要红）
- [ ] `budget.py` 摘要段记账注释更新为瘦身后真实值（现状 86.6KB 的推导说明保留为历史；不改 `MODULE_SUMMARY_BYTES` 数值）
- [ ] `python -m pytest -q` 全绿（本张不改预筛装配点，覆盖率 6 条 xfail 应仍是 xfail）

## 答复（code-review 双轴整改，2026-09-08）

- **Standards 轴**：`to_line` / `to_line_lean` 三段逐字重复 → 提取 `_decision_segments()` 两形态共用；「行渲染唯一实现」文档串失真 → `ManifestSummary` / `build_manifest_summaries` / `CONTEXT.md` 同步改为「两种形态、同一出口」；半角冒号 → 全角；`_bounded_first_sentence` 位置 → 移到 `ManifestSummary` 旁；测试钉 `"能"*100` → 改用 `LEAN_SUMMARY_SENTENCE_CHARS` 常量；平台过滤自造 → 改走 `selection.filter_manifests_by_platform` 单源并注明与 `_fit_summaries_by_wire` 的 `+1` 同口径；字节账测试与 `test_recommend_real_library_budget` 同轴问题 → 保留（两层不同：本张守「摘要段装得下全库」，那条守「完整 payload ≤ 网关预算」），文档串写明关系。
- **Spec 轴**：首句切分取的不是最早切点（84/93 条「；」先于「。」）→ 改 `_bounded_first_sentence` 取最早出现者，补 `adc` 红证用例；记账数字取自自复制探针 → 探针改走生产实现（`lean_copy().to_line()`），实测数字更新为 stm32 28071B / mspm0 28062B（生产口径）。
- **形态挂载**：spec 原写「`to_line()` 语义不变 + 新增瘦身渲染方法」，实现取「`lean_line` 字段 + `to_line()` 双形态」。取舍：渲染出口唯一（预筛算字节与实际渲染必须同源，否则截断判断与实际行形态漂移）；代价是标志进 `__eq__`，已由工单 02 的 `_same_summary_content` 修复（见 02）。
- **范围说明**：本张的 diff 与工单 02 在同一工作树内并发推进，Spec 轴评审看到的 7 文件 diff 含 02 的改动；提交按工单拆分（本张只含 manifest / budget / test_manifest / CONTEXT）。
