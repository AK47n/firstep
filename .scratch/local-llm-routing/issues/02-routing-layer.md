# 02 — 路由层：文本三调用走本地、其余走 DeepSeek

**What to build:** 配置了本地端点后，赛题简介 / 模块简介 / 参考素材简介三个纯
文本摘要调用自动走本地模型，其余调用（模块推荐、骨架生成、编译修复、提炼判定、
澄清等）仍走 DeepSeek；本地服务不可用时大声失败并给出可操作提示（不自动回退
DeepSeek）。不配置本地端点 = 行为与现状逐字节一致。

**Blocked by:** 01（依赖 `local_llm_base_url` / `local_llm_model` 字段）

**Status:** ready-for-agent

## 验收

- [ ] `RoutingLLM` 实现既有 `LLM` Protocol：本地方法集
      {summarize_topic, summarize_module, reference_summarize} → local 实例，
      其余所有方法 → remote 实例；方法集外方法绝不落到 local。
- [ ] `build_llm(config)`：本地 base_url 为空 → 返回普通 DeepSeekLLM（非
      RoutingLLM，零回归断言）；非空 → RoutingLLM（remote = 主配置实例，
      local = 同一 api_key + 本地 base_url / 本地 model 的实例）。
- [ ] webapp 的 `AppContext.llm_factory` 默认值指向 `build_llm`；archive 路径
      的 llm_factory 闭包基于同一 `_llm(ctx)`，路由自动覆盖全链路（无需额外改）。
- [ ] 本地失联：RoutingLLM 捕获 local 委托抛出的最终 LLMError，包装附明确提示
      「本地模型服务不可用：请启动 Ollama，或到设置页清空本地模型配置以改用
      DeepSeek」，错误类别（kind）保持；沿用既有重试机制；**不**自动回退远程。
- [ ] 测试：RoutingLLM 派发（两个记录型 fake，断言每个方法落到的委托）；
      build_llm 无字段零回归 / 有字段配置正确；webapp 级（注入 fake factory +
      本地配置）本地组端点走 local、远程组端点走 remote。全量 pytest + mypy 绿。

## 文件边界

- LLM 模块（RoutingLLM / build_llm / 本地方法集常量 / 失联提示文案单源）。
- webapp 的 `AppContext.llm_factory` 默认值与 `_llm` 接线（一行级改动）。
- 测试：llm 路由单元 + test_webapp.py；沿用 `tests/fakes.py` 注入（不真连本地）。
- 不动 config 字段语义（01 已定）、不动前端。
