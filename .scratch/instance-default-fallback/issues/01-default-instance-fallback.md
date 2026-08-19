# 01 — 多实例默认兜底：AI 没猜实例时按平台默认自动填入

**要做什么：** 推荐结果里命中多实例模块（led）但 AI 没猜实例时，done 载荷自动带平台默认实例清单（stm32 红/黄/绿 3 实例、mspm0 单实例），前端实例卡直接显示可改；AI 猜了用 AI 结果；没选多实例模块不落键（旧载荷逐字节不变）。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] selection 新增 `default_instance_plan(platform)`（单源默认清单：stm32 红黄绿 / mspm0 单实例 / 空平台空元组）
- [x] `run_recommendation` 加 platform 参数（webapp recommend 路由传 chosenPlatform）；装配兜底：无 instances + platform 非空 + 命中多实例模块 → 补默认清单
- [x] 测试：兜底（stm32 3 实例 / mspm0 1 实例）/ AI 实例原样 / 无多实例模块不落键 / 空 platform 不兜底 / 单源断言（5 新增）；webapp 既有断言原样绿
- [x] 渲染零回归：test_module_multi_instance 65 全绿（红黄绿默认渲染 == 默认文件）
- [x] 全量 pytest 绿（2019）；CONTEXT.md「多实例」词条补兜底口径；backlog.md 第 2 项标记已实现
