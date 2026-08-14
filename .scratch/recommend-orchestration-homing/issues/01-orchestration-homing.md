# 01 — 推荐两阶段编排归位 selection（/api/recommend 路由瘦身）

**What to build:** 把 /api/recommend 路由闭包里的两阶段编排（澄清先行 → question 终态不发 round → 空进收敛 → done 载荷组装与条件附加）收成 selection.py 的单一域函数，路由只剩取参 + 转调 + sse 包装；补结构测试防回退。

**Status:** resolved（2026-08-11 实施提交，1044 绿 + mypy 干净，验收全勾；PR #44 已合 main d365348——2026-08-14 收尾改正状态字段）

## 现状（已核实）

- webapp.py:541-646 路由：run 闭包（:594-640）持有全部编排——llm.clarify 澄清（:596-600，有疑问 → emit.question 收尾不发 round）；select_modules_convergent（:601-612，progress_emitter=emit.progress、manual_fulltexts=topic.manual_fulltexts）→ selection.questions 非空 → emit.question 收尾；done 载荷组装（:613-639：modules/requirements、topic.key 非空才附加 topic_id + related_modules、references = auto（锚定命中，平台属性带出）+ manual（手动选）并集去重手动优先标注）；:633-639 emit.done。docstring :547-574 ~90 行即事实 spec。
- selection.py 已有原语：select_modules_convergent（:704，收敛循环含两级注入 + 逐句对照 + 进度旁路）、manual_reference_admission（:268）、associated_references（:192）。装配点 resolve_topic_context（generator.py:121 TopicContext）已备好全部素材（problem_text / manifest_summaries / suggestions / read_fulltext / manual_fulltexts / key / related_modules / references / manual_references）。
- 归位先例：工单 C1（4ec4ac8）已把模型类 + 收敛循环归 selection；clarify-first（85417bc）把两阶段组合带回路由——本轮是 C1 的续章。TYPE_CHECKING 引用先例：reference_library.py:53-56（llm 仅类型注解）。
- events.py:28-37 事件词表单源（EVENT_ROUND / EVENT_CONVERGED / EVENT_DONE / EVENT_QUESTION / EVENT_ERROR）；sse.py:76 SseEmitter、:120 run_sse（run 抛错补发 error 终态，终态保证归运行器）。

## 实施

1. **selection.py** 新增域函数（放模块推荐域段落，与 select_modules_convergent 相邻）：
   `run_recommendation(topic: TopicContext, llm: LLM, clarifications: Sequence[tuple[str, str]] = (), *, emit: SseEmitter) -> None`
   - TopicContext 仅 TYPE_CHECKING 引用（`if TYPE_CHECKING: from .generator import TopicContext`），运行时鸭子类型；SseEmitter 运行时导入 sse（无环）。
   - 语义 = 路由闭包逐字迁移：clarify(topic.problem_text, clarifications) 有疑问 → emit.question({"questions": [...]}) 收尾返回；空 → select_modules_convergent（references=topic.suggestions、reader=topic.read_fulltext、progress_emitter=emit.progress、manual_fulltexts=topic.manual_fulltexts）→ questions 非空 → emit.question 收尾；否则组装 done 载荷（modules/requirements 逐字、topic.key 条件附加 topic_id+related_modules、references auto+manual 并集去重手动优先、platform 随条目带出）→ emit.done。
   - 返回 None（终态一律由域函数发，路由不再分支）。
2. **webapp.py** /api/recommend 路由瘦身：run 闭包 = `run_recommendation(topic, _llm(context), clarifications, emit=emit)` 单行；删闭包内编排与载荷组装（:594-639）；docstring 压回契约摘要（请求体契约 / 事件形状 / 错误语义保留，编排细节指向 selection.run_recommendation）。
3. **结构测试防回退**：断言 webapp.py 中 /api/recommend 路由函数体不含 `llm.clarify` / `select_modules_convergent` / `emit.done` / `emit.question` 调用（按仓库结构测试惯例：源码切片或 AST，参照 test_autocommit.py 的断言风格）——编排回路由即红。
4. **测试**：test_selection.py 用 FakeLLM 直测 run_recommendation——(a) 澄清有疑问 → 只发 question 终态、无 round 事件；(b) 澄清空 + 收敛 questions 非空 → question 收尾；(c) 收敛成功 → done 载荷逐字断言（modules/reasons、requirements、topic.key 非空带 topic_id+related、references auto+manual 并集去重手动优先标注）；(d) topic.key 空（no-topic 形）→ 载荷无 topic_id/related。test_webapp.py 既有 recommend HTTP 测试保持全绿（行为不变，无需改断言）。

## 验收

- `python -m pytest` 全绿 + `mypy src` 干净。
- 结构测试红 = 编排回路由（防回退）。
- 真机（可选）：8001 推荐一条 question 终态路径 + 一条收敛 done 路径，事件形状与合入前逐字一致（比对前端渲染）。

## 文件边界

`src/contest_generator/selection.py`、`src/contest_generator/webapp.py`、`tests/test_selection.py`、`tests/test_webapp.py`

**明确不动的：** /api/recommend 请求体契约与事件形状（question/done payload 逐字不变）；select_modules_convergent 签名与语义；TopicContext 定义（generator.py 不碰）；llm.py（clarify 归 llm 机械提取层，不动）；events.py；sse.py。
