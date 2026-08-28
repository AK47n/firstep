# 05 — 修复：「做这一步」点击后无即时反应（实机反馈）

**要做什么：** 用户点「做这一步」后看不到明确反馈，不确定任务是否已开始。根因：① 点击后仅更新任务区顶部一行小字（tasks-status），**任务卡本身不变化**（按钮仍亮、无「进行中」徽章）；② `tasksExecute` 的 busy 守卫是**静默 return**——若恰有任务在执行中，点击直接被吞掉且无任何提示。

**被谁阻塞：** 无（纯前端 bugfix；承接 stepwise-deepen/02）。

**状态：** resolved

- [x] `tasksExecute`（ui/generate-tasks.js）：点击瞬间 `setTaskStatusLocal(taskId, "doing")` + `tasksRender()`——卡片立刻出现「进行中」徽章、执行按钮消失（taskCardActions doing = []），不等 SSE 首帧；重渲染后回填已读取的补充说明框内容（note 不会被清空丢失）。
- [x] busy 守卫改为显式提示：`toast("info", "有任务正在执行中，请等当前任务完成后再操作")`，不再静默吞点击。
- [x] 失败路径：catch 后 `await tasksReload()` 重读磁盘清单——后端失败会恢复 previous 状态落盘，乐观 doing 必须回填为磁盘真相（否则「进行中」挂死误导用户）。
- [x] 状态文案首帧升级为「已开始执行：AI 实现本任务中…」→ 后续 SSE 事件继续推进（任务执行/编译/修复/验证/总结）。
- [x] 测试：JS 全量 530 passed；`node --check` 语法校验通过。纯函数层无改动（改动全在 UI 胶水层，js 测试不覆盖 glue 属既有边界）。

**实机路径**：点「做这一步」→ 卡片立即变「进行中」（按钮消失）→ 顶部状态行逐步推进 → done 后卡片回填真实状态 + 结果面板（编译徽章 / 步骤报告 / diff / 回滚）。

**提交：** 见 git 历史（工单 05 提交）。
