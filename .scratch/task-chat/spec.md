# 任务卡序号（建议顺序）+ 每卡多轮对话区

- 状态：已拍板（2026-08-27 两轮 ask_user_question）
- 关联前序：task-progress（01-03）、task-feedback（01-03）

## 问题陈述

任务推进已有「任务卡」机制（拆解 → 逐卡执行 → 编译验证 → 上板反馈）。用户提出两点缺口：

1. **序号**：任务卡现只显示 `t1..tn` 小标，用户看不出「从哪一步开始做方便」。用户希望 AI 按「方便做的顺序」给任务排序并显式标序号，用户从上往下做顺手；**但不强制**——仍然可以跳着做（现状 `depends_on` 只作展示与排序用途、无强制闸，已满足「不强制」）。
2. **每步沟通**：每一步都要有让用户发表想法/纠正的对话框。现状沟通通道是「做这一步」时的一次性补充框（note）+ 执行后的上板反馈（feedback），**没有多轮对话**——用户说想法、AI 先回应（可行/不可行/怎么改）、用户确认后执行的这一环缺失。

用户原话（大意）：「给任务卡标一个序号，用户不一定要按这个顺序做，但可以先把任务卡按方便做的顺序顺下来，用户从上往下做方便，没有限制必须按顺序做。还有一定要保证每一步用户都能沟通——每一步都要有让用户发表想法或纠正的对话框。」

## 方案

### 1. 序号（AI 建议顺序）

- 任务卡标题行显式呈现「第 N 步（建议顺序）」——N = 清单内的序号（1 起，即现有 id 顺序 t1..tn 的展示层换算，id 不变、不引入新排序字段）。
- 任务网格顶部加一行声明：「建议按序号从上往下做（AI 按方便实现的顺序排）；不强制顺序，可跳着做」。
- 不提供手动重排（用户拍板）；`depends_on` 语义不变（展示与排序用途）。

### 2. 每卡多轮对话区（「和 AI 商量」）

- 每张任务卡新增「和 AI 商量」按钮（状态 doing 时禁用）→ 点击展开卡内对话区（buy-discuss 讨论区样式复用：历史消息列表 + 输入框 + 发送）。
- 对话 = 用户发表想法/纠正/提问，AI 逐轮回应（新端点 `/api/tasks/discuss`，同步；每轮一次 LLM 调用）。
- **采纳**：对话区每条 AI 回复下挂「采纳这条结论」按钮 → 点击把该回复全文写入任务级字段 `dialog_note`（落盘 `.contest_tasks.json`，刷新不丢）→ 任务卡显示「已采纳对话结论」徽标 + 摘要；再次采纳覆盖，按钮「取消采纳」清空（text=空串）。
- **执行注入**：`dialog_note` 非空时，下一次「做这一步」的 LLM prompt 增加独立段【用户沟通结论（采纳自对话）】（插在 note 段之后、feedback 段之前）——用户确认后的结论自动带进下一步执行。采纳后仍可继续对话（执行后调整想法再采纳）。
- 对话历史不落盘（会话级内存态，与 buy-discuss 同款；刷新丢历史但采纳结论落盘）。

## 用户故事

1. 拆解任务后，任务卡显示「第 1 步（建议顺序）」…「第 N 步（建议顺序）」，网格顶部声明不强制顺序。
2. 用户可以按顺序从上往下做，也可以任意跳着做（现状行为不变）。
3. 每张任务卡（未执行/执行后）都能点「和 AI 商量」展开对话区。
4. 用户发表想法/纠正后 AI 立即回应（可行性、对任务实现的影响、修正建议）。
5. 用户对某条 AI 回复点「采纳这条结论」→ 该卡显示「已采纳」徽标与摘要（刷新保留）。
6. 采纳后点「做这一步」，AI 的实现以对话结论为准（prompt 带独立段）。
7. 采纳错了可「取消采纳」或再采纳一条覆盖。
8. 对话区与「做这一步」互不阻塞：先聊、后做、做完继续聊都行。
9. 补充框（note）与上板反馈（feedback）通道保持不变，语义不变。
10. doing（执行中）任务不可开对话区（不可人工操作不变量）。

## 实现决策

- **D1 dialog_note 字段**：`Task.dialog_note: str = ""`（frozen dataclass，to_dict/from_dict 带出读回、缺省兼容旧清单；`_with_task_status` 重建 Task 时保留——None=保留原值，与 note/iterations 同款参数）。
- **D2 执行注入零协议变更**：`llm.execute_task` 签名不动——`run_task` 已传 `task.to_dict()`，prompt 拼装 `_task_execute_user_prompt` 直接读 `task.get("dialog_note", "")`；段模板：【用户沟通结论（采纳自对话，按此修正实现）】。空 = 无该段（既有形状逐字节不变）。
- **D3 采纳端点**：`POST /api/tasks/dialog-adopt`（同步）`{output_dir, task_id, text}`；text 非字符串 → TaskError 400；text 空串 = 清除。域编排 `set_task_dialog_note(output_dir, task_id, text) -> {"task","plan"}`（照 apply_task_status 先例：读→update→write，路由薄壳）。
- **D4 讨论协议**：`llm.discuss_task(task, problem_text, qa_text, requirements, module_interfaces, main_c, history) -> TaskDiscussion{reply: str}`（照 discuss_buy_options 先例：协议 + DeepSeek 实现（_retry_parse json_mode）+ RoutingLLM remote 转发 + 系统提示词 + user prompt 段拼装，history 段复用 `_discuss_history_segment` 字符帽先例）。输出只有 reply（讨论是沟通不是选型——不做 review 结构化；回应结构由系统提示词引导：先判可行性，再给影响与建议）。
- **D5 讨论端点**：`POST /api/tasks/discuss`（同步）`{output_dir, task_id, message, history}`（history = [{role, content}] 旧→新，前端积累，照 buy-discuss 校验：非数组/条目非对象/role 词表外/content 非字符串 → TaskError 400）；服务端 `_load_revision_context` 读题面/Q&A/需求/接口/main.c（现读 main_c 照 execute 先例）；任务须存在。LLMError → 502。telemetry 照常（collector → try/finally `recent_llm_workflows.add_completed`）。
- **D6 事件**：events.py 登记 `EVENT_TASK_DISCUSS = "task_discuss"`（词表单源；同步端点不发射 progress 事件，与 buy-discuss 同款）。
- **D7 前端**：fx/task.js 纯函数（序号 `taskOrderLabel(index)`、对话区 `taskDialogAreaHTML`、采纳徽标 `taskDialogAdoptedBadge`、历史/回复渲染）；ui/generate-tasks.js 胶水（每卡 state `{dialogOpen, dialogBusy, dialogHistory, dialogReply}`；「和 AI 商量」toggle；发消息 POST /api/tasks/discuss；采纳/取消 POST /api/tasks/dialog-adopt；执行成功/改标后重渲染保留对话区）；index.html 仅 CSS（0 构建约束）。
- **D8 序号呈现**：`taskCardHTML(task, index)` 标题行「第 N 步（建议顺序）· {title}」；`tasksGridHTML(tasks)` 顶部声明文案；任务状态/行动作/进度全部不变；进度文本可加「建议顺序 第 N 步 → 下一步」不强制（维持最小改动：只做序号+声明）。

## 测试决策

- test_task_progress.py：dialog_note 往返（to_dict/from_dict）、旧清单读回缺省空串、_with_task_status 保留/替换、set_task_dialog_note 落盘/清除/未知任务/清单未拆解。
- test_llm.py：_task_execute_user_prompt 带 dialog_note 段（位置在 note 后、feedback 前）/空=无段；discuss_task 协议方法（DeepSeek 解析、RoutingLLM remote、reply 空→LLMError、PROTOCOL_METHOD_NAMES）；prompt 快照。
- test_webapp.py：/api/tasks/dialog-adopt 200/400（text 非字符串/任务不存在）；/api/tasks/discuss 200/400（缺 message/history 非法/任务不存在）+ 502（LLMError）。
- tests/js/task.test.mjs：taskOrderLabel、taskDialogAreaHTML（展开/历史/采纳徽标）、采纳按钮显隐；fx-guard DOMAINS 登记新导出。
- fakes.py：FakeLLM/RecordingLLM 加 discuss_task。

## 范围外

- 不做手动拖拽/上下移重排（用户拍板 AI 建议顺序）。
- 不做对话历史落盘（会话级；采纳结论落盘）。
- 不做强制「每步必须先对话」（对话框是能力不是门禁）。
- 不改 note/feedback 通道语义；不改任务状态机；不加新任务状态。
- 不做单卡多对话线程/对话评分。

## 补充说明

- 序号 = 展示层换算（index+1），无新排序字段，id/depends_on 零改动。
- 采纳按钮挂在 AI 回复上（结论 = AI 回复全文）；用户想用自己的原话作为结论时，可把原话再发一轮让 AI 确认后采纳（或直接发送消息后采纳下一轮回复）。
