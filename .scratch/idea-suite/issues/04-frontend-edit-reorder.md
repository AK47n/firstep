# 工单 04：任务清单微编辑 + 调序前端 UI（fx/task.js + ui/generate-tasks.js + index.html + 测试）

Status: resolved

> 修订说明（双轴评审）：`taskMoveButtonsHTML` 工单签名 (index, total) → 实现
> (task, index, total)——委托必须知道换的是哪张卡（与既有 .btn-task-* 带
> data-task 同构），注释已说明；本地校验补 0 / 越界序号拦截；重新拆解后
> taskEditOpen 清空（防旧编辑态残留展开新卡）。

## 目标

实现 spec 第 5-6 条用户故事前端：任务卡「✏️ 编辑」表单 + 操作行「↑ / ↓」按钮（边界禁用），提交后重渲染。

## 交付

- **fx/task.js**（纯函数 + esc + window 桥 + fx-guard 登记）：
  - `taskEditFormHTML(task, opts)`：标题/描述输入框、依赖文本（逗号分隔 1 起序号，空 = 无依赖）、验收方式下拉（compile/manual）、评分点文本（逗号分隔，可空）；保存/取消按钮（data-task-action="edit-save|cancel"）。
  - `taskMoveButtonsHTML(index, total)`：↑/↓ 按钮（data-task-action="move-up|move-down"）；首卡 ↑ 禁用 / 末卡 ↓ 禁用。
  - taskCardHTML 操作行集成（编辑按钮 data-task-action="edit" 切换表单显示；移动按钮）。
- **ui/generate-tasks.js**：
  - 委托 .btn-task-edit 切换卡片编辑态（渲染 taskEditFormHTML）；edit-save → 收集字段 → POST /api/tasks/idea/edit → tasksReload 重渲染 + toast；edit-cancel 收起。
  - 委托 move-up/move-down → POST /api/tasks/idea/move → tasksReload（重排序即显示顺序）。
  - busy 守卫 toast（既有惯例）；跨簇重置收起编辑态。
- **index.html**：CSS `.task-edit-form` / `.task-move`（按钮行内）；无新容器（表单渲染进卡内）。
- 测试：task.test.mjs 新用例（表单渲染/值回填/边界禁用/转义）；fx-guard 登记新导出；JS 全量绿。

## 验收

1. 点「✏️ 编辑」：卡内出现表单，当前值回填；保存 → 卡片更新并落盘；取消 → 收起不变。
2. 改依赖后卡片 deps 行更新；改验收方式后徽章与「上板」语义同步。
3. 「↑ / ↓」：换序即时生效；首卡 ↑ / 末卡 ↓ 禁用。
4. 编辑/调序不动 needs_redo/轮次历史（重渲染后仍显示）。
5. 全部 JS 测试绿（既有 559 + 新增）。
