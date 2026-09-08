# 07 — 选中代码快捷动作（解释 / 加中文注释 / 重构）

**要做什么：** 选中代码后的浮动按钮（现「问 AI」）升级为动作菜单：解释 / 加中文注释 / 重构 / 问 AI（原有）。前三者 = 固定 prompt 模板 + 选中代码上下文（复用 selectionContextText 的路径/语言/行号/代码形态），点击后经既有 `/api/tasks/idea/chat/send` 发送并自动切到 AI 面板；AI 回复若含 `<DIFF>` 走既有预览→应用闭环。零后端改动。

**被谁阻塞：** 无（菜单浮层样式若 06 已实现则复用其组件，否则本工单自带最小浮层）。

**Type:** task
**Status:** resolved

## 实现要点

- 新 fx 纯件：动作模板常量 + buildActionPrompt(action, ctx)（node 单测）；动作名中文展示（解释 / 加中文注释 / 重构 / 问 AI）。
- 浮动按钮点击 → 菜单展开 → 选择动作发送；发送后 showPanel('ai') 并聚焦输入；原「问 AI」行为不变。
- 模板含「只输出修改后的完整片段/只解释不修改」约束，降低 diff 解析失败率；失败回退纯文本显示。

## 实现决策备注（双轴评审后回写，workflow.md step 4）

- **菜单组件复用（工单 :5 授权）**：06 的树右键菜单浮层抽为共享 `ui/context-menu.js`（openContextMenu/closeContextMenu + 三通道关闭 + 菜单内右键拦截），树菜单与动作菜单共用；06 的 `treeCtxMenuHTML`（渲染归共享组件）删除、`treeCtxClamp` 泛化移入 fx/overlay.js 更名 **menuClamp**（浮层纯件族归位——通用组件不再依赖专用树模块）。
- **busy 门控（评审整改）**：快捷动作直发与输入框发送同口径——runSelectionAction/sendAiText 均查 busy（AI 回应中再点动作 toast「请稍候」，防并发双写）；sendMessage 先查 dir 再清空输入（dir 缺失草稿保留）。
- **动作后按钮可见性（评审整改）**：文档级 click 捕获隐藏浮动按钮时排除 `.code-ctx-menu`（点菜单项不再误隐藏；选区仍在，动作后按钮保持显示）。
- **失败回填对称（评审整改）**：sendAiText 失败仅在输入框为空时回填 prompt——输入框发送路径清空后回填可重发；动作直发不清输入框，用户草稿保持不动。
- **模板契约（评审整改）**：<DIFF> 块 JSON 形状从「注释」模板抽为 `DIFF_FORMAT_HINT` 常量，注释/重构两模板共用（重构单独调用时 AI 也看得到契约，降低解析失败率）；契约文字与 parseAiDiff 校验跨文件镜像为记录项（LLM 提示词与 JS 校验天然双份）。
- **id 单源（评审整改）**：`AI_ASK_ACTION_ID` 导出——分发判定与清单共用，ui 层不再硬编码 `"ask"` 字符串。
- **空选区防护（评审整改）**：buildActionPrompt 对 ctx 缺省/空字段归一（path "" / 行号 1 / code ""），不落字面 undefined。
- **CONTEXT.md 词表（记录项）**：fx/ai-actions.js、ui/context-menu.js 与「选中代码快捷动作」概念未入词表（词表懒更新，后续轮次补录）。
- **不做什么**：不自动发送「问 AI」、不做动作历史/多选合并、不改服务端 prompt（模板只在前端拼装）。

## 验收 checklist

- [x] 选中代码 → 浮动按钮出菜单 → 四个动作；前三者发送消息文本 = 模板 + 选区上下文（CDP 断言：chat/send 捕获 history 末条含模板 + 【代码引用 · main.c · 第 3-5 行】）。
- [x] AI 回复含 <DIFF> 时预览/应用/409 流程与现有一致（冒烟断言「预览改动」按钮出现）；非 diff 回复纯文本展示、无预览按钮（解析不破坏）。
- [x] 未选中时不出现浮动按钮（不回归）；选择清空菜单关闭 + 按钮隐藏（冒烟 5a/5b）。
- [x] node 单测 buildActionPrompt（三种动作 + 空选区防护 + ask/未知回退）；CDP 冒烟 smoke-07 13/13（日志 smoke-07.log 存证）。全量 1232 pass；回归 smoke-06 19/19、smoke-05 11/11。
