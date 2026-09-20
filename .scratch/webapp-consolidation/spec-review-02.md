# 工单 webapp-consolidation/02 — Spec 轴评审（固定点 HEAD 68638782，工作树）

评审对象：`git diff HEAD` 的 `src/contest_generator/webapp.py` + 新文件
`tests/test_llm_run.py`（规格：`.scratch/webapp-consolidation/spec.md` 第二节 +
`issues/02-llm-run-single-seam.md`）。

结论：**三件套收口忠实、语义零变化、无越界**（25 处调用点 / 20 处派发 / 5 处视觉 / 7 处裸
`_llm(context)` 全部对上；`finally` 顺序逐字一致；`settle()` 幂等有 `_settled`；webapp 里四件
事原始出现各 1 次——评审独立 AST 计数 1/1/1/1）。发现 3 处缺项 + 3 处实现问题（1 处硬伤）。

## (a) 要求了但缺失 / 只做一半

1. **`__enter__` / `__exit__` 完全没实现（硬伤）**。spec.md:82「`__enter__` / `__exit__` 让
   `with` 退出即结算」、工单计划第 32 行同款；实现只有 `__init__/llm/settle`（AST 核实 0 个
   上下文管理方法、全文 0 处 `with llm_run`）。工单验收里的「`with` 退出结算」被显式
   `settle()` 用例顶替——上下文管理器路径零用例。
2. **推荐路由的「双收集器 + 抛错两结算」无直测**（工单验收点名）：实现照旧正确
   （`webapp.py:2189–2192` 主流先、视觉后，包住装配后的整个 try），但只有既有 HTTP 契约用例
   间接覆盖，异常路径无用例。
3. **「视觉 5 处零派发」只有间接证据**：缝直测用自造 run（工作流名 `vision-describe`）验证，
   不经 5 个真实路由；工单要求用记录型工厂断言。

## (b) 范围蔓延

实质为零（仅 2 行注释里过时的数字）。路由结构 / 端点 / 事件 / 载荷 / 前端零改动，符合「不做
route 分册」。

## (c) 做了但实现有问题

1. **守卫的「恰好一处」比工单判据弱**：`_triple_sites` 按 owner 函数去重
   （`owner not in sites[probe]`），同一函数里写两遍照样绿——实测重复两遍仍返回
   `{'collector': ['route'], …}`；`dispatch` 探针带 `len(node.args) >= 2`，未来 `_llm(context)`
   裸调用长回去不会被认成违规；`settle` 探针认属性名（不认宿主链）。
2. **红证数字与工单口径不一致**：工单表 25/20/22/26 是原始调用点，守卫量的是去重 owner
   （实测 HEAD = 23/20/21/23）；`verify-02-homing.txt` 脚注解释了，但工单表本身没改。
3. **合成片段红证成立但不完整**：四键等值断言确实红；片段尾部 `_llm(ctx)` 不贡献 dispatch
   （这是**刻意口径**——裸调用不是三件套派发）。「不缓存」由「工厂被调用 ≥2 次且拿到同一对
   对象」钉住，另有既有两条 HTTP 用例。

## 处置（实施者回填，2026-09-20）

- (a)1：**改文档而不加回协议**（spec 与工单对应段已更正并写明理由：25 处调用点每处本来就有
  明确结算位置，再养一套 `with` 惯用法是同一件事的第二种写法，且引入无人使用的 API——同轮
  Standards 轴正以 Speculative Generality 判掉另一个未用面）。
- (a)2：补 `test_recommend_settles_both_observations_even_when_the_body_raises`（真实端点上让
  正文抛错，断言观察面板里 `["vision-qa", "recommend"]` 两条都在且先后正确；两个收集器各造
  一条观测，否则 `add_completed` 对空观测是空操作、用例会假绿）。
- (a)3：补 `test_vision_extract_never_dispatches_the_llm_factory`（真实 `/api/extract` +
  记录型工厂 → 断言零派发）。
- (c)1：判据改成**按每一个调用点数**（不去重），并补 `test_llm_triple_guard_counts_every_call_site`
  （同函数写两遍 → 红）与 `test_bare_llm_call_is_not_a_dispatch`（裸调用不算派发的口径）。
- (c)2：工单判据表按实测口径更正为 23/20/21/23 并注明两种口径的区别。
- (c)3：保留原口径（裸 `_llm(ctx)` 不是三件套派发），已在测试里显式钉住。
