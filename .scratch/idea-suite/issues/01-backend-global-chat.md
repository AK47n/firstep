# 工单 01：全局工程级商量后端（idea_chat / llm / task_progress / webapp / events + 测试）

Status: resolved

## 目标

实现 spec（.scratch/idea-suite/spec.md）第 1-4 条用户故事后端全链路：
工程级多轮对话（历史落盘 `.contest_idea_chat.json`）→「采纳为全局结论」（note 落盘）→ **全局结论注入后续每步任务执行与直接修正**。

## 交付

- **idea_chat.py（新模块）**：`IdeaMessage{role, content, at}`、`IdeaChat{version, generated_at, messages: tuple, note: str}` + `IDEA_CHAT_FILENAME = ".contest_idea_chat.json"`；load/save/empty chat 工厂/append_message/set_note；坏 JSON → TaskError 400 中文（照 task_progress 清单文件先例）；旧版本缺字段 → 默认值。
- **llm.py**：
  - `Protocol.discuss_global_idea(...) -> TaskDiscussion`（json_mode；reply 空 → LLMError 重试；RoutingLLM passthrough remote）。
  - `TASK_GLOBAL_DISCUSS_SYSTEM_PROMPT`（工程总顾问：结合题面/需求/清单现状/接口/当前 main.c/工程级全局结论；不直接改代码）。
  - `_global_idea_user_prompt`（想法 → 题面/Q&A/需求/评分点/清单摘要（复用 _idea_plan_summary）/接口/main.c/全局结论 note/历史；各段 _truncate_content）。
  - `execute_task` 与 `apply_idea_fix` 加可选参数 `global_note: str = ""`（默认空 = 既有调用形状逐字节不变）；`_task_execute_user_prompt` / `_idea_fix_user_prompt` 在 feedback/受影响段后、赛题前插【工程级全局结论】段（非空才有）。
- **task_progress.py**：`run_task` / `run_direct_fix` 加 `global_note: str = ""` 透传 llm 调用（默认空兼容）。
- **events.py**：`EVENT_IDEA_CHAT = "idea_chat"`（send 同步端点观察面板用，照 EVENT_TASK_DISCUSS 先例）。
- **webapp.py**：
  - `POST /api/tasks/idea/chat/read`：{output_dir} → {chat}（无文件 = 空 chat，不 400）。
  - `POST /api/tasks/idea/chat/send`：{output_dir, message} → 装配题面/需求/接口/清单（照 /api/tasks/discuss）→ llm.discuss_global_idea → 追加 user+assistant 落盘 → {reply, chat}。
  - `POST /api/tasks/idea/chat/adopt`：{output_dir, text}（空串 = 清除）→ {chat}。
  - `/api/tasks/execute` 与 `/api/tasks/idea/fix`：读 chat note → `global_note` 传给 run_task / run_direct_fix。
- **tests/fakes.py**：FakeLLM / RecordingLLM 加 `discuss_global_idea`；execute_task / apply_idea_fix 加 global_note 参数记录（含调用断言）。
- 测试：test_idea_chat.py（模型/落盘/坏 JSON/append/set_note）+ test_llm.py（discuss_global_idea 解析/prompt 段/global_note 注入段/路由）+ test_task_progress.py（run_task/run_direct_fix global_note 透传断言）+ test_webapp.py（chat 三路由 + execute/fix 注入）新增；全量 pytest 绿。

## 验收

1. chat/send 一轮：`.contest_idea_chat.json` 落盘含 user+assistant 两条消息；再发一轮追加（消息全量保留）。
2. chat/adopt：note 写入落盘；空串清除；read 返回 messages+note。
3. run_task 带 global_note：llm.execute_task 收到非空 global_note；prompt 含【工程级全局结论】段；空 note 时无该段（既有测试形状不变）。
4. run_direct_fix 同样透传。
5. chat/read 无文件 → 空 chat（200，不 400）；坏 JSON → 400 中文。
6. 全量 pytest 绿（既有 2670 + 新增）。
