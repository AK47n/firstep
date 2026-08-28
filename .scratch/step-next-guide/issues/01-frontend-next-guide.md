# 01 — 前端：做完一步提示「下一步」+ 滚动高亮下一张卡

**要做什么：** 任务执行成功（SSE done）后，当前卡内追加「下一步 → tN：标题」提示行；下一张待执行卡（清单顺序上当前卡之后第一个 pending/failed）平滑滚动到视口中央并高亮 2.4s；无剩余待执行则不提示不滚动。纯前端，无后端改动。

**被谁阻塞：** 无（spec 已定口径）。

**状态：** claimed

**实现要点：**
- [ ] `fx/task.js`：新增导出 `nextTaskHint(plan, currentId)`（→ `{id, orderIndex, title} | null`；顺序 = 清单下标，当前卡之后第一个 status∈{pending,failed}，其余状态跳过，找不到 → null）与 `taskNextHintHTML(plan, currentId)`（→ `下一步 → tN：<esc(title)>` 的 `.task-next-hint` div HTML，空 → ""）。
- [ ] `ui/generate-tasks.js`：tasksExecute 的 SSE done 处理中（tasksRender + tasksRenderResult 之后）：`taskNextHintHTML(tasks.plan, taskId)` 非空 → `tasks-grid.querySelector('[data-task-id="<taskId>"]')` `insertAdjacentHTML("beforeend", hint)`；再取 `nextTaskHint` 找下一张卡 → `scrollIntoView({behavior:"smooth", block:"center"})` + `classList.add("task-card-highlight")`，2.6s 后移除。
- [ ] `index.html`：CSS `.task-next-hint`（accent 色小字行）+ `.task-card-highlight`（`@keyframes task-next-glow` 2.4s box-shadow 描边脉冲；`@media (prefers-reduced-motion: reduce)` 禁用动画）。
- [ ] `tests/js/task.test.mjs`：nextTaskHint 5 条（命中第一个 pending / 跨状态命中 failed / 全不可执行 null / currentId 缺失 null / 返回 orderIndex 与 title）+ taskNextHintHTML 3 条（转义 / 前缀与序号 / 空串）。
- [ ] `tests/js/fx-guard.test.mjs`：DOMAINS 登记 nextTaskHint / taskNextHintHTML。
- [ ] 探针：`.scratch/step-next-guide/probe-next-hint.mjs`（真实页注入卡 + hint 行 + 高亮类，验证渲染与 CSS 生效）。
- [ ] 全量 `node --test tests/js/*.test.mjs` 绿。

**答复：** 已完成。fx/task.js 新增 `nextTaskHint`（当前卡后第一个 pending/failed；其余状态跳过；找不到/入参缺失 → null）与 `taskNextHintHTML`（`下一步 → tN：<esc(title)>` `.task-next-hint` 行；无下一步 → ""）；ui/generate-tasks.js done 后调 `guideNextTask(taskId)`（hint 注入当前卡 beforeend + 下一卡 scrollIntoView center + `task-card-highlight` 2.4s 动画、2.6s 移除；失败轮不引导）；index.html 加 `.task-next-hint` / `@keyframes task-next-glow` / reduced-motion 禁用。测试：task.test.mjs 新增 2 个测试（含 spec 评审补的「之后全为不可执行 → null」断言）+ fx-guard 登记 2 导出；JS 全量 544 绿；探针 probe-next-hint.mjs ALL PASS。双轴评审整改：①selector 改 CSS.escape（评审：未转义 id 拼 attr 选择器有 SyntaxError 风险）②window 桥补挂两新导出 ③CSS 主题色硬编码 rgba → color-mix(var(--accent)) ④setTimeout 加 isConnected 守卫 ⑤nextTaskHint 只算一次。

**验收：** spec「验收」三条全过。
