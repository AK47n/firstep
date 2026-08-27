# 工单 03：前端每卡对话区 + 序号呈现

**要做什么：**任务卡「第 N 步（建议顺序）」序号 + 不强制声明；每卡「和 AI 商量」多轮对话区（展开/历史/发送/采纳/已采纳徽标）。

**被谁阻塞：**工单 01（dialog-adopt 端点）、工单 02（/api/tasks/discuss 端点）。

**状态：** resolved（双轴评审通过 + 整改）

## 验收标准

- [x] fx/task.js 新纯函数（window 桥 + fx-guard DOMAINS 登记）：`taskOrderLabel(index)`（「第 N 步（建议顺序）」）、`taskDialogAreaHTML(task, st)`（对话区：历史消息 + AI 回复 + 输入框 + 发送按钮；doing 状态禁用/隐藏入口；空 history 提示「可以告诉 AI 你的想法或纠正」）、`taskDialogAdoptHTML(task)`（已采纳徽标 + 摘要（前 30 字）+ 取消采纳按钮；未采纳 = 空串）、采纳按钮渲染在每条 AI 回复下（`data-task-adopt`）；`taskCardHTML(task, index)` 标题行改为「第 N 步（建议顺序）· {title}」（序号 = index+1，id 不变）；`tasksGridHTML(tasks)` 顶部加声明：「建议按序号从上往下做（AI 按方便实现的顺序排）——不强制，可跳着做」。
- [x] ui/generate-tasks.js：每卡 state `{dialogOpen, dialogBusy, dialogHistory, dialogReply}`（Map 键 = task id，渲染时 fallback）；「和 AI 商量」按钮显隐（pending/skipped/verified/unverified/failed 可见；doing 不可见/禁用）；toggle 展开/收起；发送 → POST /api/tasks/discuss（history 积累；busy 防重；空消息提示）；采纳 → POST /api/tasks/dialog-adopt（采纳后 task 更新 + 徽标渲染）；取消采纳 → 同端点 text=""；执行成功（tasksRenderResult）/改标后重渲染保留已展开对话区与历史；渲染纯函数化（buildTask 时 index 透传）。state 实为 `{open, busy, history, draft}`（draft = 输入框未发送内容，重渲染不丢）。
- [x] index.html：对话区样式 CSS（.task-dialog-box 系列，0 构建，样式复用 .sugg-discuss-*）；无 JS 胶水留 index.html（全部迁入 ui/fx）。
- [x] 测试：tests/js/task.test.mjs（taskOrderLabel/taskDialogAreaHTML 空与历史/采纳徽标/taskCardHTML 序号标题）；既有测试断言更新（taskCardHTML/tasksGridHTML 签名带 index）。
- [x] 浏览器冒烟（Playwright：.scratch/task-chat/e2e-browser.mjs，mock /api/tasks/discuss + dialog-adopt 真写盘）：加载桌面 2021F 工程 → 任务卡显示「第 N 步（建议顺序）」+ 顶部声明 → 展开对话区 → 发送消息 → AI 回复 → 采纳 → 徽标出现 → 刷新后采纳仍在 → 取消采纳恢复原状 → ALL PASS（10 项）。
- [x] 中文 commit。

## 评审记录

双轴 code-review（git diff cd00038...94425fd）：Standards 0 硬违规；Spec c1 → **已整改：taskOrderLabel 补「（建议顺序）」**（spec 三处均要求用户可见文案「第 N 步（建议顺序）」，原实现只有「第 N 步」；JS 断言/E2E 同步更新）。Spec c2 → **已整改：采纳按钮补 `data-task-adopt` 属性**（与 data-task/data-idx 并存，事件委托仍按 class）。判断项：dialogInputHTML 参数 s → st 已改名；30 字截断 = spec「前 30 字」定数（注释注明非魔数）。
