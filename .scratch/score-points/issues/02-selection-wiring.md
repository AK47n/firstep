# 02 — 推荐链路接线与兼容

**要做什么：** 学生完成题面推荐后，评分点作为推荐结果的一部分随现有收敛、缓存和完成载荷传递；旧缓存没有评分点字段时仍保持原有推荐行为。

**被谁阻塞：** 01 — 评分点模型与解析。

**状态：** resolved

- [x] 将评分点加入现有推荐链路的模型输出与域层结果，不新增独立 LLM 调用。
- [x] 评分点与功能需求共用当前题面句子编号和收敛循环上下文。
- [x] 收敛结果稳定时评分点随结果返回，且不要求评分点与功能需求一一对应。
- [x] 推荐缓存写入可选评分点字段；读取旧缓存时缺省为空且不触发补跑。
- [x] 评分点层解析异常不改变原有推荐成功、失败和缓存行为。
- [x] 增加推荐、收敛、缓存和完成载荷的回归测试。

## 实施说明

在 `ModuleSelection` 增加可选 `score_points` 字段，`build_module_selection` 从 requirements 与 plain modules 两种旧/新输出契约解析评分点；非法评分点按工单 01 解析器约定降级为空，不影响模块推荐。推荐提示词在既有单次模块选择调用的输出契约中声明可选评分点，`run_recommendation` 仅在有评分点时加入 done 载荷，保持无评分点旧载荷逐字兼容。评分点不参与功能需求收敛键，因此不会改变收敛轮次；缓存复用 done 载荷原样透传，旧缓存没有评分点字段时无需补跑。

## 测试结果

- `py -m pytest -q tests/test_selection.py tests/test_llm.py tests/test_recommend_cache.py`：358 passed
- `py -m mypy src/contest_generator/selection.py src/contest_generator/llm.py`：通过
- 代码评审：已按 Standards / Spec 双轴完成，未发现明确问题。
