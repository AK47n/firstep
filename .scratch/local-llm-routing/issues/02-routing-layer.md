# 02 — 路由层：文本三调用走本地、其余走 DeepSeek

**What to build:** 配置了本地端点后，赛题简介 / 模块简介 / 参考素材简介三个纯
文本摘要调用自动走本地模型，其余调用（模块推荐、骨架生成、编译修复、提炼判定、
澄清等）仍走 DeepSeek；本地服务不可用时大声失败并给出可操作提示（不自动回退
DeepSeek）。不配置本地端点 = 行为与现状逐字节一致。

**Blocked by:** 01（依赖 `local_llm_base_url` / `local_llm_model` 字段）

**Status:** resolved

## 验收

- [x] `RoutingLLM` 实现既有 `LLM` Protocol：本地方法集
      {summarize_topic, summarize_module, reference_summarize} → local 实例，
      其余所有方法 → remote 实例；方法集外方法绝不落到 local。
- [x] `build_llm(config)`：本地 base_url 为空 → 返回普通 DeepSeekLLM（非
      RoutingLLM，零回归断言）；非空 → RoutingLLM（remote = 主配置实例，
      local = 同一 api_key + 本地 base_url / 本地 model 的实例）。
- [x] webapp 的 `AppContext.llm_factory` 默认值指向 `build_llm`；archive 路径
      的 llm_factory 闭包基于同一 `_llm(ctx)`，路由自动覆盖全链路（无需额外改）。
- [x] 本地失联：RoutingLLM 捕获 local 委托抛出的最终 LLMError，包装附明确提示
      「本地模型服务不可用：请启动 Ollama，或到设置页清空本地模型配置以改用
      DeepSeek」，错误类别（kind）保持；沿用既有重试机制；**不**自动回退远程。
- [x] 测试：RoutingLLM 派发（两个记录型 fake，断言每个方法落到的委托）；
      build_llm 无字段零回归 / 有字段配置正确；webapp 级（注入 fake factory +
      本地配置）本地组端点走 local、远程组端点走 remote。全量 pytest + mypy 绿。

## 实施备注（2026-08-17）

- llm.py：`LOCAL_LLM_METHODS` / `LOCAL_LLM_UNAVAILABLE_MESSAGE` 常量单源 +
  `RoutingLLM`（`_delegate` 读常量派发、`_local_call` 三文本摘要共用失联包装）+
  `build_llm`（本地 base_url 空 → DeepSeekLLM 零回归；非空 → RoutingLLM，
  local = `replace(config, base_url=本地, model=本地)`）。本地 model 空串时沿用
  主 model（请求体 model 非空，防御取舍，测试钉死）。
- webapp.py：`AppContext.llm_factory` 默认值 `DeepSeekLLM` → `build_llm`
  （一行级改动；archive 闭包 `llm_factory=lambda: _llm(context)` 未动，自动覆盖）。
- tests：fakes.py 增 `RecordingLLM`（13 方法记录型 fake）；test_llm.py 派发 /
  常量↔派发同源 / 失联包装 kind 保持 / 远程失败原样 / build_llm 三件套；
  test_webapp.py 默认值接线 + 本地组端点走 local + 远程组端点走 remote +
  webapp 层失联 502。
- code-review 双轴：核心结论「常量装饰性」已修（派发读常量 + 同义反复测试改
  行为断言）；RecordingLLM 与 FakeLLM 方法面重复、build_llm 测试探私有 config
  两处留痕（判例：测试专用 fake / 工厂接线无公共缝，判据可接受）。
- 全量 1812 pytest 绿 + mypy src 47 文件干净 + node:test 17 绿。

## 文件边界

- LLM 模块（RoutingLLM / build_llm / 本地方法集常量 / 失联提示文案单源）。
- webapp 的 `AppContext.llm_factory` 默认值与 `_llm` 接线（一行级改动）。
- 测试：llm 路由单元 + test_webapp.py；沿用 `tests/fakes.py` 注入（不真连本地）。
- 不动 config 字段语义（01 已定）、不动前端。
