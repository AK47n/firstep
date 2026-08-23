# Spec：本地模型错误提示分类——区分「Ollama 未启动」与「模型加载失败（内存不足）」

## 问题（用户报告）

澄清阶段报错「本地模型服务不可用：请启动 Ollama」，但 Ollama 实际在运行——真实原因是
qwen3-coder:30b 权重 18.5GB 超出本机 15.2GB 内存，llama-server 分配 11.6GB buffer 失败崩溃
（`llama-server process has terminated: exit status 1: ggml_backend_cpu_buffer_type_alloc_buffer:
failed to allocate buffer of size 11598741504`）。提示文案误导用户去「启动 Ollama」——
Ollama 在跑，重启无用。

## 方案

`RoutingLLM._wrap_local_error`（llm.py:2362）按错误特征选提示文案：

1. **新常量 `LOCAL_LLM_LOAD_FAILED_MESSAGE`**（模型加载/运行失败）：Ollama 在运行但
   llama-server 崩溃（特征关键词：`llama-server` / `failed to allocate` / `exit status`）→
   提示「模型加载或运行失败……常见原因：模型过大超出内存……请换更小的模型（如 qwen3:8b）
   或到设置页清空本地模型配置以改用 DeepSeek」。
2. **既有 `LOCAL_LLM_UNAVAILABLE_MESSAGE`**（Ollama 未启动）：连接被拒绝
   （`连接被拒绝` / `connection refused`）→ 提示「请启动 Ollama」。
3. 其他形态 → 通用原文案兜底。
4. 分类函数 `_local_error_hint(exc) -> str` 模块级（可直测）；`_wrap_local_error` 调它。
   kind 保持、不自动回退远程、防御嵌套路由——既有行为不变。

## 范围外

- 不改路由逻辑（本地方法集/远程直通不变）；不改配置；不做自动回退远程。
- 不改其他错误文案。

## 验收

- llama-server 崩溃形态（500 + llama-server/failed to allocate）→ 消息含「模型加载或运行
  失败」「换更小的模型」，不含「请启动 Ollama」。
- 连接拒绝形态 → 消息含「请启动 Ollama」（既有测试保持绿）。
- 未知形态 → 通用兜底文案。
- 全量测试绿 + mypy 干净。
