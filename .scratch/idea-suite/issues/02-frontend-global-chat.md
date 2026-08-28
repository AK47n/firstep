# 工单 02：全局工程级商量前端 UI（fx/task.js + ui/generate-tasks.js + index.html + 测试）

Status: claimed

## 目标

实现 spec 第 1-3 条用户故事前端：任务推进区「全局商量」入口（多轮对话区，历史从 /chat/read 加载、发送 /chat/send、采纳 /chat/adopt），每条 AI 回复挂「转成任务 / 转成修正 / 采纳为全局结论」，当前全局结论徽标（含清除）。

## 交付

- **fx/task.js**（纯函数 + esc + window 桥 + fx-guard 登记）：
  - `globalChatHTML(chat, st)` / `globalChatMessageHTML`：历史渲染（用户/AI 分行，at 时间），每条 AI 回复挂三按钮（data-global-action="task|fix|adopt"，data-global-text）；输入行 + 发送按钮；st.busy 时输入禁用。
  - `globalNoteBadgeHTML(note)`：「工程级全局结论」徽标 + 清除按钮（data-global-action="clear"）；空 note → ""。
- **ui/generate-tasks.js**：
  - `chatState{busy, open, chat}`；`tasksChatToggle`（展开时 /chat/read 加载）；`tasksChatSend`（POST send → 更新 chat → 重渲染）；`tasksChatAdopt(text)`（POST adopt → 更新徽标）；`tasksChatConvert(action, text)`（转任务 = tasksIdeaAnalyze(text, autoLand="new_task") 复用讨论漏斗；转修正 = 同款 direct_fix）。
  - 事件委托（生成任务卡地区域内 .btn-global-chat-*）；跨簇重置（revise-context-loaded / tasks-invalidated）关区清状态。
  - 徽标区渲染 +「采纳/清除」toast 反馈。
- **index.html**：tasks-box 内「全局商量」折叠区容器（#tasks-global-chat + #tasks-global-note + 开关按钮）+ CSS（沿用 idea-result / .sugg-discuss 变量风格）。
- 测试：task.test.mjs 新用例（聊天渲染/消息分行/按钮显隐/note 徽标/转义）；fx-guard 登记新导出；JS 全量绿。

## 验收

1. 展开「全局商量」：历史消息完整渲染（含 AI 回复三按钮）；无历史 → 空引导文案。
2. 发送一轮：输入清空、消息追加、落盘（刷新后仍在）。
3. 点「采纳为全局结论」：徽标出现该回复全文；「清除」后消失。
4. 点「转成任务 / 转成修正」：走既有 idea 漏斗通道（分析 → 落地），落地后结果卡正常。
5. 全部 JS 测试绿（既有 559 + 新增）。
