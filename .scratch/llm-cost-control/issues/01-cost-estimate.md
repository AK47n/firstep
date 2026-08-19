# 01 — LLM 费用估算（单价表 + 仪表盘费用行）

**要做什么：** 在现有 LLM 观测数据上加一层费用估算：可配置单价表（DeepSeek 按官方价目、本地 0 成本），设置页可覆盖单价；设置页「最近 LLM 工作流」卡片每行显示估算费用与本地路由节省额，标注估算性质。

**被谁阻塞：** 无——可立即开始（llm-observability-dashboard/03 已提供 usage 数据）

**状态：** resolved

- [x] `llm_pricing.py`：`estimate_llm_cost(usage, prices)` 纯函数 + `LLMPriceTable`（deepseek / local 两套单价，本地默认 0）；默认单价常量（参考官方定价页，注释标明可改）。
- [x] AppConfig 增可选单价覆盖字段（config.json 读写，缺省用内置默认）；设置页 UI 可编辑单价（留空 = 维持当前，全空 = 恢复默认）。
- [x] `llm_recent_workflows.py` 快照与 `/api/llm-workflows/recent` 载荷增估算字段（est_cost_actual / est_cost_deepseek / est_savings）。
- [x] 前端 summary 行显示「cost ¥x.xx（全 DeepSeek ¥y.yy，省 ¥z.zz）」；脚注标注「估算的参考值，以官方账单为准」；零费用不显示。
- [x] 测试：估算纯函数（单价/缺字段/小数/零）；快照载荷含估算字段；前端费用行格式化 node 用例。

## Notes

- `llm_pricing.py`：`estimate_llm_cost` 返回精确浮点（不 round——多次调用聚合时小金额要能累加，展示层再舍入）；`LLMPriceTable.from_dict` 校验 provider/数值/负数；`price_tables_from_config` 部分覆盖语义（只写 deepseek 就只覆盖 deepseek，local 仍零成本）；`price_tables_to_config` = 完整生效表序列化（GET /api/settings 直接展示当前生效单价）。
- 估算派生在 `llm_recent_workflows.estimate_workflow_cost`：按每次调用实际 provider 单价累加（actual）、全部按 DeepSeek 单价对照（counterfactual）、节省 = 差值；provider 表外按 0 计；无 usage 的调用贡献 0。`attach_cost_estimates` 浅拷贝注入 `est` 字段，原载荷不污染。
- config：`AppConfig.llm_prices`（None = 内置默认）；save 时 None 不写键（配置文件保持最小，既有精确 JSON 断言不扰动）；`llm_prices` 非 dict 大声失败，条目级脏数据消费侧静默跳过（展示层旁路）。
- 前端：设置页 AI API 卡 4 个单价输入（DeepSeek/本地 × 输入/输出）；`collectLlmPrices()` 收集（每 provider 全空 = 不覆盖，任一填写则按填的值 + 未填沿用当前生效值）；summary 行 `formatWorkflowCost`（实际/对照/节省，节省 > ¥0.005 才显示，都为零不显示）；脚注「估算的参考值，以官方账单为准」。
- 默认单价仅为参考：2026-08-18 DeepSeek 大幅调价（最高 1100%，峰谷定价），设置页可覆盖是硬需求。
- 验证：pytest 1882 全绿（+22）、`node --test tests/js/` 全绿、`mypy src` 51 文件干净。
