# 工单 01：本地失联提示按错误特征分类（llm.py 单文件切片）

Status: resolved

## 实施与评审记录
- tdd：先写 _CrashingLocal/_UnknownFailureLocal 假件 + 2 个断言（崩溃形态换模型提示 / 未知形态兜底），import 失败红 → 实现后绿。
- 实现：LOCAL_LLM_LOAD_FAILED_MESSAGE 常量 + _local_error_hint 分类函数（llama-server/failed to allocate/exit status → 加载失败文案，其余通用）+ _wrap_local_error 改用 hint、嵌套防御扩为两文案。
- 全量 2177 通过；mypy src 59 文件干净（tests 存量 16 错非本次引入，stash 验证）。
Depends: 无
Blocks: 无

## 目标

本地模型错误提示区分两类：Ollama 未启动（连接拒绝）→「请启动 Ollama」；
llama-server 崩溃（模型过大/内存不足）→「请换更小的模型或清空本地配置」。

## 改动点（src/contest_generator/llm.py + tests/test_llm.py）

1. 新常量 `LOCAL_LLM_LOAD_FAILED_MESSAGE`（LOCAL_LLM_UNAVAILABLE_MESSAGE 之后）。
2. 模块级 `_local_error_hint(exc: LLMError) -> str`：特征关键词分类——llama-server /
   failed to allocate / exit status → 加载失败文案；连接被拒绝 / connection refused →
   原文案；其余兜底原文案。
3. `RoutingLLM._wrap_local_error` 改用 `_local_error_hint(exc)`（防御嵌套检查保持）。

## 测试（tdd 先红）

- test_llm.py：新假件 `_CrashingLocal(RecordingLLM)`（summarize_topic 抛
  `LLMError("DeepSeek API 返回 500：...llama-server process has terminated: exit status 1:
  ggml_backend_cpu_buffer_type_alloc_buffer: failed to allocate buffer of size 11598741504...",
  kind=ERROR_KIND_NETWORK)`）：
  - 断言包装消息含 LOCAL_LLM_LOAD_FAILED_MESSAGE（「模型加载或运行失败」「换更小的模型」），
    不含「请启动 Ollama」。
  - 断言 kind 保持 network、remote 零调用。
- 既有 `test_routing_llm_local_failure_wraps_with_actionable_message`（连接被拒绝 → 原文案）保持绿。

## 验收

- 全量 pytest 绿 + mypy 干净；真实场景（Ollama 在跑但模型崩溃）提示指向换模型而非启动 Ollama。
