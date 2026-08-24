# 02 — AI 起名英文化 + 粘贴题面路径英文目录名

**要做什么：** 粘贴题面（无 topic_id）生成工程时，目录名由 AI 起的英文短名
决定（如 `Auto_Car`）：新增 LLM 方法 `name_topic_english(problem_text) -> str`
（纯文本、同 summarize_topic 的重试/截断协议，不走本地模型集），webapp 的
`_resolve_generation_output_dir` 粘贴题面分支改调它；HTTP 语义不变（AI 失败
→ 502）。

**被谁阻塞：** 01（命名决策一致，先有字典/兜底语义）

**状态：** resolved

- [x] `src/contest_generator/llm.py`：`LLM` Protocol + 各实现 +
      `TOPIC_EN_NAME_SYSTEM_PROMPT` 新增 `name_topic_english`（文本模式、
      `_retry_parse` 兜底、超长截断同款）；RoutingLLM 直通 remote（不进
      LOCAL_LLM_METHODS）
- [x] `src/contest_generator/webapp.py`：粘贴题面分支改调
      `name_topic_english`，目录名 = 英文短名（go 过 windows_safe）
- [x] `tests/fakes.py`：FakeLLM 补 `name_topic_english`
- [x] `tests/test_llm.py`：`name_topic_english` 文本模式 / 截断 / 重试 /
      RoutingLLM 派发（非本地集）测试
- [x] `tests/test_webapp.py`：粘贴题面分支 fake 断言 → 英文目录名；
      历史赛题分支断言 → `2024H_Auto_Car`
- [x] 相关测试文件全绿

**验收记录（2026-08-24）：** webapp 4 个受影响测试更新（组装 / 碰撞唯一化 /
历史赛题 / AI 失败 502），llm 新增 4 个单测（文本模式 / 截断 / 重试 / 空输出
拒绝）+ 派发扫描加 name_topic_english（落 remote）；PROTOCOL_METHOD_NAMES
同步。
