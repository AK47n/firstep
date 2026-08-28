# 02 — 评分点覆盖总览（前端聚合视图）

**要做什么：** 任务推进区顶部（资源总览旁）新增「评分点覆盖总览」——每个题面评分点一行（id + 分类标签 + 分值 + 描述截断 + 覆盖它的任务列表），无任务覆盖的行标红「⚠ 无任务覆盖」；任务引用了评分点清单外的 id → 黄色「未识别引用」警示行；同时把任务卡评分点标注的数据源统一为落盘的 `plan.score_points`（历史目录场景自动补全「基础/发挥 x 分」标注）。

**被谁阻塞：** 01 — 评分点定义随任务清单落盘（数据源）。

**状态：** claimed

- [ ] `fx/task.js` 新增导出 `scoreRefsOverviewHTML(plan)`——纯函数（esc 全转义、无副作用）；空评分点/空清单 → `""`；未知引用（`tasks[].score_refs` 里的 id 不在 `plan.score_points`）→ 黄色警示行
- [ ] `index.html`：`#tasks-resources` 之后新增 `#tasks-scorepoints` 容器（`class="hidden" style="margin-top:8px"`）；样式 `.score-point-row` / `.score-point-miss`（红）/ `.score-point-unknown`（黄）/ `.score-chip` / `.score-miss-note` / `.score-unknown-note`（参照 `.res-*` 先例）
- [ ] `ui/generate-tasks.js` `tasksRender`：与 resBox 同模式渲染 scoreBox（`innerHTML` + `classList.toggle("hidden", !html)`）；`opts.scorePoints` 改为 `plan.score_points` 落盘优先、会话 `scorePoints` 回退
- [ ] `tests/js/task.test.mjs`：`scoreRefsOverviewHTML` 单测（有覆盖/部分覆盖/全未覆盖/未知引用/空/null/转义/分类标签与分值格式）+ `taskCardHTML` 落盘值同源断言；`tests/js/fx-guard.test.mjs` 导出清单追加 `scoreRefsOverviewHTML`
- [ ] `node --test "tests/js/*.test.mjs"` 全过；浏览器探针 `.scratch/score-coverage/probe-score-coverage.mjs`（playwright）：容器可见性、未覆盖行红标、未知引用行、plan-read 重载后视图仍在、截图确认
