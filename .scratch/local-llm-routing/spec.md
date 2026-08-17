# 本地模型路由（local-llm-routing）

## Problem Statement

DeepSeek API 涨价。用户的 RTX 5070 Ti Laptop（12GB 显存）可本地跑
Qwen2.5-Coder-7B。零代码 spike（`.scratch/local-llm-spike/`）实测证明：

- **协议层全通**：base_url 换到本地 OpenAI 兼容端点即可；`response_format`
  json_object 被接受；100% GPU offload、87 tok/s。
- **纯文本摘要类调用质量达标**：赛题简介、模块简介、参考素材简介三类，中文
  摘要准确、无脑补。
- **JSON 结构化调用被卡死**：本地 7B 时好时坏地把 JSON 包进 ```` ```json ````
  围栏，项目严格解析器不剥围栏 → 失败重试仍失败、大声抛错。
- **main.c 骨架生成质量不稳定**：有时守纪律全 TODO（好），有时幻觉不存在的
  函数 / 未初始化变量（违背"打开就能编译"）。

结论：**不能整体替换**。需要把"本地能干好的文本摘要组"路由到本地、其余难度
高的调用继续走 DeepSeek。

## Solution

工具支持配置一个本地 LLM 端点（base_url + 模型名）。配置后，**三个纯文本
摘要调用（赛题简介 / 模块简介 / 参考素材简介）自动走本地模型**，其余调用仍走
DeepSeek。不配置 = 行为与现状逐字节一致（零回归）。本地模型不可用时大声失败
并给出可操作提示。设置页可填写 / 清空本地端点。

## User Stories

1. As 用户，I want 在设置页填写本地模型 base_url 和模型名，so that 不需要手改配置文件。
2. As 用户，I want 配置后赛题简介 / 模块简介 / 参考素材简介走本地模型，so that 这些高频文本调用不花 API 钱、不受限流影响。
3. As 用户，I want 其余调用（模块推荐、骨架生成、编译修复、提炼判定、澄清等）仍走 DeepSeek，so that 质量不受本地模型能力拖累。
4. As 用户，I want 不配置本地模型时行为与现在完全一致，so that 默认体验零变化。
5. As 用户，I want 本地服务没启动时收到明确报错（提示启动 Ollama 或到设置页关闭本地配置），so that 我知道是环境问题而不是工具坏了。
6. As 用户，I want 设置页能清空本地配置恢复纯 DeepSeek，so that 我可以随时关掉本地路由。

## Implementation Decisions

- **新增可选配置字段** `local_llm_base_url` / `local_llm_model`（缺省空串 =
  本地路由关闭，行为逐字节不变）。`api_key` 复用主配置（本地服务不校验）。
  `load_config` / `save_config` / `AppConfig` 扩展；可选字段非字符串时大声失败。
- **RoutingLLM（组合式）**：实现既有 `LLM` Protocol，持 `remote` 与 `local`
  两个 LLM 实例 + 一个本地方法集。方法在本地集内 → `local`，其余 → `remote`。
  本地方法集 = **{summarize_topic, summarize_module, reference_summarize}**
  （纯文本、spike 实测质量达标；这是能力事实，硬编码为常量，不做用户可配）。
- **构造接线**：`build_llm(config)` —— 本地 base_url 为空 → 返回普通
  DeepSeekLLM（≡ 现状）；非空 → 返回 RoutingLLM（remote = 主配置实例，
  local = `replace(config, base_url=本地地址, model=本地模型)` 的实例）。
  webapp 的 `llm_factory` 默认值指到 `build_llm`；archive 路径的 `llm_factory`
  闭包基于同一个 `_llm(ctx)`，路由自动覆盖全链路。
- **本地失联（大声失败）**：RoutingLLM 捕获 local 委托抛出的最终 LLMError，
  包装附明确提示「本地模型服务不可用：请启动 Ollama，或到设置页清空本地模型
  配置以改用 DeepSeek」，错误类别（kind）保持。沿用既有重试机制（网络类指数
  退避），不自动回退 DeepSeek（用户裁决）。
- **设置页**：/api/settings GET 返回新字段、PUT 接受新字段（缺省/空 = 关闭）；
  前端设置表单加两个输入框（本地 base_url / 本地模型），保存立即生效。
- **常量单源**：本地方法集与失联提示文案在 llm 模块唯一出处，测试引用。

## Testing Decisions

- **测试缝（最高既有缝）**：webapp 的 `AppContext.llm_factory` 注入 +
  `tests/fakes.py` 既有 fake LLM。路由测试用两个记录型 fake 断言派发，不真连
  本地服务。
- **单元**：RoutingLLM —— 三个文本方法走 local、其余方法走 remote；方法集
  外的任何方法都到 remote。
- **单元**：build_llm —— 无本地字段时返回**非** RoutingLLM（零回归断言）；
  有本地字段时返回 RoutingLLM 且两端配置正确（local 用本地 base_url/model）。
- **配置**：新字段 roundtrip、缺省空串、类型校验大声失败。
- **webapp**：/api/settings GET/PUT 带新字段；注入 fake factory + 本地配置
  后，本地组端点走 local fake、远程组端点走 remote fake。
- **回归**：无本地配置的默认路径走既有全部测试（pytest 全量 + mypy 全绿），
  逐字节不回归。

## Out of Scope

- JSON 组本地化（clarify / 简介校验 / 模块推荐 / 编译修复 / 提炼判定等）——
  需先做解析层"剥围栏"改动且质量未测，留后续。
- main.c 骨架 / 冒烟生成本地化 —— spike 实测质量不稳，留 DeepSeek。
- 本地失联自动回退 DeepSeek —— 用户已裁决大声失败。
- 每调用记录来源（本地/远程）的诊断 UI。
- 其他本地模型（Qwen3 等）调优、负载均衡、健康检查。

## Further Notes

- spike 记录在 `.scratch/local-llm-spike/`（spike.py + spike-result.txt）。
- 本地运行时已就绪：Ollama 0.32.13 + `qwen2.5-coder:7b-instruct`
  （魔搭 GGUF → `ollama create`，32k context，12GB GPU 100% offload）。
  Ollama OpenAI 端点 `http://localhost:11434/v1`，`response_format` 被接受。
- 留痕：7B 围栏包 JSON 不稳定（同提示词时好时坏）——这是将来 JSON 组本地化
  的第一道坎，届时在解析层剥围栏，不归本 spec。
