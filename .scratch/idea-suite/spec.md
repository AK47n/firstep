# 想法套件（idea-suite）：全局商量 / 清单微编辑 / 草稿箱

## 问题陈述

「灵活修正」（idea-fix）合入后，三个高频场景仍无入口：

1. **工程级持续商量**：想法分析（discussion）是单轮漏斗，任务商量绑定单卡——用户想针对**整个工程**连续追问（整体架构要不要加滤波 / 赛道策略取舍 / 某方案对不对），现有入口都装不下；聊出的结论也没处存（采纳结论目前是任务级的）。
2. **清单不可微调**：AI 拆解的任务卡标题/描述/依赖/顺序只能看不能改——不满意的措辞或顺序只能整份「重新拆解」（进度全废）。
3. **想法无处攒**：现场连冒多个念头，一次只能分析一个，分析完就过去。

用户原话（拍板）：「全局工程级商量」「把 AI 结论转成任务/修正并能采纳为全局结论（后续任何一步执行都注入）」「清单微编辑 + 上移/下移调序」「想法草稿箱（工程目录落盘）」。

## 目标

1. **全局工程级商量区**（不绑任务卡，多轮）：AI 工程总顾问结合题面/需求/清单现状/接口/当前 main.c 回答；每条 AI 回复挂「转成任务 / 转成修正」（复用 insert/fix 通道）与「采纳为全局结论」（写入工程级注记）；**全局结论注入后续每步任务执行与直接修正**。
2. **任务清单微编辑 + 调序**：改标题/描述/依赖/验收方式；上移/下移调顺序（id 不变，依赖引用稳定）；不动 status/needs_redo/轮次历史。
3. **想法草稿箱**：工程目录落盘；逐条「分析这条」、删除、批量逐条分析。

## 用户故事（验收口径）

1. 任务推进区有「全局商量」入口：多轮对话，历史**落盘**（`.contest_idea_chat.json`，刷新/重开不丢）。
2. 每条 AI 回复挂「转成任务」「转成修正」——复用现有 insert/fix 后端（idea 文本 = 该条回复）。
3. 每条 AI 回复挂「采纳为全局结论」——全文写入工程级注记（`note`，最新覆盖）；卡上/区上显示当前全局结论 + 清除按钮。
4. **全局结论注入**：此后任何任务执行（run_task）与直接修正（run_direct_fix）的 prompt 含独立【工程级全局结论】段；未采纳 = 无该段（逐字节兼容）。
5. 任务卡有「✏️ 编辑」：改标题/描述/依赖（1 起序号，转 id）/验收方式；非法输入 400 中文；改后 status/needs_redo/轮次历史保留。
6. 任务卡操作行有「↑ / ↓」：相邻换序；首卡 ↑ / 末卡 ↓ 禁用；排序后网格即时重排；id 不变（依赖引用与 needs_redo 不受影响）。
7. 想法输入区可「存入草稿」；草稿区列表 = 每条「分析这条」（填入分析流程）/「删除」；「全部逐条分析」= 顺序逐条调用分析（状态行显示 第 N/总）。
8. 草稿落盘 `.contest_ideas.json`（工程目录）；无草稿 = 空数组；重复文本去重（同文本只存一条）。

## 实现决策

### 后端

- **idea_chat.py（新模块）**：`IdeaMessage{role, content, at}`、`IdeaChat{version, generated_at, messages: tuple[IdeaMessage,...], note: str}` + `IDEA_CHAT_FILENAME = ".contest_idea_chat.json"`；load/read/save（照 task_progress 清单文件先例：坏 JSON → TaskError 400 中文；未知字段忽略；旧版本缺省补默认）；`append_message` / `set_note` / `clear`（纯函数或域编排）。
- **llm.py**：新协议 `discuss_global_idea(idea, problem_text, qa_text, requirements, score_points, module_interfaces, main_c, plan, history)` → `TaskDiscussion{reply}`（复用讨论产物形状；json_mode；reply 空 → LLMError 重试）；`TASK_GLOBAL_DISCUSS_SYSTEM_PROMPT`（工程总顾问：结合题面/需求/清单现状（id/标题/状态/依赖摘要）/接口/当前 main.c/工程级全局结论 note 回答；不直接改代码）；`_global_idea_user_prompt`（想法 → 题面/Q&A/需求/评分点/清单摘要/接口/main.c/全局结论/历史——各段 _truncate_content）；RoutingLLM passthrough remote。
- **llm.py 注入**：`execute_task` 与 `apply_idea_fix` 加可选参数 `global_note: str = ""`（默认空 = 既有调用形状逐字节不变）；`_task_execute_user_prompt` / `_idea_fix_user_prompt` 在 feedback/受影响段后、赛题前插【工程级全局结论】段（非空才有）。
- **task_progress.py**：`run_task` / `run_direct_fix` 加 `global_note: str = ""` 透传 llm；`update_task_fields(plan, task_id, ...)` 纯函数（title/description 非空、verify 词表、depends_on 1 起序号转 id 越界拒收、score_refs 字符串数组；None = 保留原值）；`move_task(plan, task_id, direction)` 纯函数（up/down 相邻换位，边界 TaskError）；保留 status/note/dialog_note/needs_redo/iterations。
- **drafts.py（新模块）**：`IdeaDraft{id, text, at}` + `IDEA_DRAFTS_FILENAME = ".contest_ideas.json"`；load/save/list/add（同文本去重）/delete；坏 JSON → TaskError 400。
- **webapp.py** 新路由（同步，除特别注明）：
  - `POST /api/tasks/idea/chat/read`：{output_dir} → {chat}（无文件 = 空 chat，不 400）。
  - `POST /api/tasks/idea/chat/send`：{output_dir, history}（最后一条 user = 本轮消息，单通道——与 /api/tasks/discuss 同构防丢消息）→ 读题面/需求/接口（照 /api/tasks/discuss 装配）+ 清单 → llm.discuss_global_idea → 成功才追加 user+assistant 落盘 → {reply, chat}。
  - `POST /api/tasks/idea/chat/adopt`：{output_dir, text}（空串 = 清除）→ {chat}。
  - `POST /api/tasks/idea/edit`：{output_dir, task_id, fields{title?, description?, depends_on?, verify?, score_refs?}} → {task, plan}（清单未拆解/任务不存在 → 400）。
  - `POST /api/tasks/idea/move`：{output_dir, task_id, direction} → {plan}。
  - `POST /api/tasks/idea/drafts/read`：{output_dir} → {drafts}。
  - `POST /api/tasks/idea/drafts/add`：{output_dir, text} → {drafts}。
  - `POST /api/tasks/idea/drafts/delete`：{output_dir, id} → {drafts}。
  - `/api/tasks/execute` 与 `/api/tasks/idea/fix` 路由：读 chat note → 传 global_note 给 run_task / run_direct_fix。
- **events.py**：`EVENT_IDEA_CHAT = "idea_chat"`（send 同步端点观察面板用，照 EVENT_TASK_DISCUSS 先例）。
- **tests/fakes.py**：FakeLLM/RecordingLLM 加 `discuss_global_idea`；execute_task / apply_idea_fix 加 global_note 参数记录。

### 前端

- **fx/task.js**：`taskEditFormHTML(task, opts)`（编辑表单：标题/描述/依赖文本（逗号分隔 1 起序号）/verify 下拉）；`taskMoveButtonsHTML(task, index, total)`（↑/↓，边界禁用）；`ideaDraftListHTML(drafts, opts)`（列表 = 分析这条/删除/全部逐条分析）；`globalChatHTML(chat, st)` + `globalChatMessageHTML`（历史渲染 + 每条 AI 回复挂三个按钮：转成任务/转成修正/采纳为全局结论 + 输入行）；`globalNoteBadgeHTML(note)`（当前全局结论徽标，含清除）——全部纯函数 + esc；window 桥 + fx-guard 登记。
- **ui/generate-tasks.js**：全局商量区（展开/收起、历史加载 /chat/read、发送 /chat/send、采纳 /chat/adopt、转任务/转修正复用现有落地通道——转任务 = 该回复作为 idea 重新 analyze 后自动 insert（讨论漏斗同款），转修正 = 同款 fix）；任务卡「编辑」表单提交 /api/tasks/idea/edit + 「↑/↓」/api/tasks/idea/move（委托 + tasksReload 重渲染）；草稿箱（存入草稿按钮、列表、分析这条 = tasksIdeaAnalyze(text)、删除、全部逐条分析循环 + 状态行）；跨簇重置（revise-context-loaded / tasks-invalidated）清 chat 区 + drafts 区状态。
- **index.html**：全局商量区容器 + 草稿箱容器 + `.idea-*` / `.task-edit-*` CSS（沿用变量）；任务卡操作行按钮在 fx 纯函数侧拼接（actions 回调）。
- 测试：tests/js 新用例（编辑表单/移动边界/草稿列表/全局聊天渲染+按钮显隐+转义）+ fx-guard；探针（实机：全局商量一轮 → 采纳 → 执行一步看注入；草稿增删；编辑/移动）。

### 测试决策

- pytest：idea_chat（模型/落盘/坏 JSON/append/set_note）+ llm（discuss_global_idea 解析/prompt 段/global_note 注入段/路由）+ task_progress（update_task_fields 校验与保留、move_task 边界/不动 id、run_task/run_direct_fix global_note 透传）+ drafts（增删查/去重/坏 JSON）+ webapp（各路由 200/400 + execute/fix 注入 global_note）+ fakes 增量。
- JS：fx 渲染断言 + 桥 + fx-guard；全量 node --test。
- 探针：全局商量（短消息一轮）→ 采纳 → 草稿增删 → 编辑/移动；不强行执行修正（成本控制，修正路径 pytest 覆盖）。

## 范围外（下一批）

- 全局结论注入生成/骨架/深化（本期只注入任务执行与直接修正）；
- 任务卡拖拽调序（本期用 ↑/↓ 按钮，交互已拍板）；
- 草稿自动批量分析进度持久化（断了重来）；
- 商量历史导出/清空按钮以外的管理功能；
- 自动连做/自动修复（与「手动逐步」决定相反，仍需重新拍板）。

## 关键文件

- 新：src/contest_generator/idea_chat.py、src/contest_generator/drafts.py、tests/test_idea_chat.py、tests/test_drafts.py
- 改：llm.py、task_progress.py、events.py、webapp.py、fakes.py、tests/test_llm.py、tests/test_task_progress.py、tests/test_webapp.py（如有对应端点测试）、front-end fx/task.js、ui/generate-tasks.js、index.html、tests/js/*、CONTEXT.md
