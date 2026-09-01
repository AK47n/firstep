# 03 — IDE 对话面板 + 选区浮动按钮（C1）

**要做什么：** IDE 内「选中代码问 AI」：
- 选区浮动按钮：编辑器（.code-ta textarea）选中文本（selectionStart≠
  selectionEnd 且非空）→ 出现浮动按钮「问 AI」（定位于高亮层选区末行
  span 右端上方——高亮层逐行 span 已存在（行定位零成本），实现前 DOM
  实测确认行 span 结构；不可行则退化为编辑器工具条按钮位置）；选区消失/
  失焦 → 按钮隐藏。**只做 UI 与定位，不引第三方选择库**。
- 对话面板 `#code-ai-chat-panel`：IDE 底部第三面板（与编译/变更面板同型
  并列：.code-compile-head/.code-compile-status 复用 + 独立 collapsed），
  head =「AI 对话」+ 状态行 + 收起钮；内容 = 消息流（用户消息含选区引用
  卡片可折叠代码块；AI 回复文本）；底部输入框 + 发送按钮 + busy 态
  （发送中禁用 + 「AI 回应中…」，复用 aiAction 横幅）。
- 发送：`/api/tasks/idea/chat/send`（{output_dir: getCodeDir(), history}
  ——历史 = read 拉取 + 本轮 user 末条，与 tasksChatSend 同契约）；发送前
  空目录 → 提示「请先打开工程目录」；失败回填 draft（tasksChatSend 先例）。
- 选区引用：点「问 AI」→ 面板打开 + 选区上下文 = selectionContextText
  （工单 01）随**下一条用户消息**附加（即：先预填「引用卡片」@输入框，
  用户打字后发送；或点击即发送上下文+提示语——实现取「预填引用+用户提问
  后发送」）。
- 历史读盘：首次展开面板 /api/tasks/idea/chat/read（同目录工程）。

**被谁阻塞：** 01（selectionContextText 拼装与解析格式）。

**状态：** resolved

- [x] 验收 1：选中代码 → 浮动按钮出现；清选区/失焦 → 消失。
- [x] 验收 2：点按钮 → 面板展开（引用卡片显示文件/行区间/代码片段）。
- [x] 验收 3：发送 → busy/横幅/消息出现（fetch 桩：返回假 chat 含 assistant
  message）；历史落盘经桩验证 sent 载荷正确（output_dir/history）。
- [x] 验收 4：无目录发送 → 提示不发送；失败 → draft 回填可重试。
- [x] 验收 5：面板与编译/变更面板同型并列可折叠，互不影响；node/smoke 全绿。

**结论：** 已落地（双轴评审 + 整改后）。

**fx/ai-chat.js（新）**：`aiChatMessagesHTML(messages, pendingText)`（.sugg-msg
气泡 + pending 乐观气泡 + 空态引导，esc 单源自 fx/core.js）；
`quoteRefParts(text)`——识别「选中代码问 AI」引用消息（首行【代码引用 ·
path · 第 a-b 行】+ ```lang 围栏）→ {path,startLine,endLine,lang,code,rest}；
user 引用消息渲染 **details 可折叠卡片**（summary = 路径与行区间、pre = 代码
片段、rest = 问题文本）；pending 同卡片化。

**ui/code-ai-chat.js（新）**：面板（#code-ai-chat-panel，与编译/变更面板同型
并列、独立 collapsed 且折叠同时隐藏输入行）；浮动按钮（惰性挂 .code-edit
内容坐标系的 .code-ai-selection-btn——选区末行 .code-hl-line 右端，随滚动
天然跟随；mousedown preventDefault 保选区；选区状态 selectionState 单源）；
`setCodeAiDir(dir)`（codeview.loadCodeDir 挂钩：面板显隐 + 读历史）；发送 =
/api/tasks/idea/chat/send（history 单通道、服务器原子轮、失败回填可重发、
busy 时 **aiActionStart/Stop("AI 对话")** 全局横幅 + 面板状态行）；
Enter 发送 / Shift+Enter 换行 / isComposing 防误发。

**index.html**：面板 DOM（change-panel 后、statusbar 前）+ CSS（公共选择器
扩展、气泡复用 .sugg-msg、引用卡片、浮动按钮、全令牌合规）；
**codeview.js**：loadCodeDir → setCodeAiDir（2 行接缝）。

**双轴评审（s1）**：
- Spec 轴 7 项：①引用卡片可折叠（已补）②复用 aiAction 横幅（已补——
  crate 先例 params-chat/generate-* 一致）③历史读盘点（记录偏离：目录
  打开即读取代「首次展开读」——打开即见历史、展开纯 UI，体验更优）
  ④空态预告「预览改动」属 C2 越界（已删句）⑤折叠未隐藏输入行（已补）
  ⑥选区末行号 off-by-one（已补：selectionEnd 前缀以 \n 结尾时 -1）——
  **修复时发现行号语义本身 = caretLineOf 数换行 +1，非 bug，是引用标注
  偏差，修正后「第 a-b 行」与切片真实行数一致**⑦按钮「右端贴合行」vs
  spec 字面「上方」（记录偏离：VS Code 式右端贴合，观感更近选区）。
- Standards 轴：0 硬违规；整改——esc 改 import fx/core.js 单源；删死类
  .code-ai-chat-scroll；删未用 toast import；四委托判定合并为 onTaEvent；
  send 禁用判定抽 setSendEnabled()。判断项记录：气泡渲染与 fx/task.js
  globalChatMessageHTML 同构不合并（task 版带转任务/转修正/采纳三按钮、
  语义不同；跨簇合并收益 < 漂移风险）。

**测试**：tests/js/ai-chat.test.mjs 10 用例（含 quoteRefParts 识别/兜底/
卡片渲染 esc）全绿；全量 node 1059 全绿；smoke-05 17 项全 PASS（fetch 桩：
面板显隐/空态/历史/浮动按钮定位/引用插入契约/发送载荷断言含引用/卡片化/
失败回填/收起展开）；smoke-02/03/04 回归全 PASS。
