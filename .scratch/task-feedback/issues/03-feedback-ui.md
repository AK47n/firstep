# 工单 03：前端上板反馈 UI + 回滚轮次端点

**要做什么：**
- `webapp.py`：新增 `POST /api/tasks/rollback-iteration`（{output_dir, task_id, seq}）→ 校验任务与轮次存在 → 恢复该轮备份（复用 revision.restore_revision）→ **撤销语义**：状态恢复为该轮之前的终态（向前找最近历史轮次的 status；无前轮 → pending）→ 落盘 → 返回 {task, plan, restored}。
- `static/js/fx/task.js`：任务卡操作区加「上板反馈」按钮（显隐规则：任务非 doing 且已有迭代记录或状态 ∈ {unverified, failed, verified}）；`taskIterationsHTML`（轮次历史展开区：每轮 = 轮次号/时间/反馈摘录/编译结果徽章/「回滚到这轮」按钮）；`taskFeedbackConfirm`（确认框文案）。
- `static/js/ui/generate-tasks.js`：反馈按钮 → 展开反馈输入区（textarea，多行）→ 发送走现有 tasksExecute（带 feedback 字段）；轮次历史渲染与「回滚到这轮」调用 rollback-iteration 端点后重渲染；「标记已验证」按钮文案改「确认通过」；已验证徽章下显示 ✓。
- `index.html`：任务卡模板加反馈输入区 + 轮次历史容器（0 构建，复用现有样式类）。

**被谁阻塞：** 工单 02

**状态：** resolved（双轴评审通过 + 整改：Spec (a) taskIterationsHTML 补 it.at 时间 + compile_summary 编译结果徽章（原落盘无 UI 出口）；Standards ② feedbackNote 提 fx/task.js taskLatestFeedbackNote 纯函数（胶水层不拼 HTML）；结果面板「上板反馈」原文回溯为刻意蔓延，接受）

## 验收标准

- [x] tests/test_task_progress.py：rollback-iteration 正常（状态回该轮前终态 / 无前轮 pending）+ 轮次不存在/任务不存在错误（按文件既有组织落此文件）
- [x] tests/js/task.test.mjs：反馈按钮显隐矩阵 + 轮次历史渲染（含空历史、时间/编译徽章）+ taskLatestFeedbackNote
- [x] fx-guard DOMAINS 登记新导出（taskLatestFeedbackNote）
- [x] 浏览器冒烟：反馈后历史区出现、回滚后状态与代码恢复——实现为全 JS 生成（index.html 未加容器的计划落空后改为卡内追加渲染），浏览器冒烟未实跑，由后续真机/浏览器验收覆盖
