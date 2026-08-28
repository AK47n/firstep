# 评分点覆盖总览（Spec）

## 问题陈述

用户（电赛学生）逐卡做完任务、准备交付时，无法确认「题面评分点是否都被覆盖到了」：现在只有**任务卡 → 评分点**方向（卡上显示 `评分点：s1（基础 3 分）`），没有**评分点 → 任务**方向的反向视图。评分点漏做（拆解遗漏 / AI 关联错 / 后续想法改掉了关联）是最常见的丢分原因，学生要自己逐卡翻、逐条对照题面才能发现。

另一个隐性问题：评分点**定义不落盘**——`.contest_tasks.json` 只存 `Task.score_refs`（id 引用），评分点完整定义（id / 分类 / 分值 / 描述）只存在于当前会话前端内存（`scorePoints`，来自推荐结果）。刷新页面或打开历史目录后，任务卡的评分点标注只剩裸 id（无「基础/发挥 x 分」），同样无法做覆盖统计。

## 方案

两件事：

1. **评分点定义随任务清单落盘**：拆解时把评分点完整定义（`{id, part, description, score}`）写入 `.contest_tasks.json` 的 `TaskPlan.score_points` 字段（新字段，旧清单缺省空，向后兼容读）。这样刷新 / 历史目录 / 换设备后，覆盖视图与任务卡标注都有数据源。
2. **新增「评分点覆盖总览」**（任务推进区顶部，资源总览旁）——题面每个评分点一行：`id + 分类标签 + 分值 + 描述（截断）+ 覆盖它的任务（tN：标题）`；**没有任何任务覆盖的评分点整行标红「⚠ 无任务覆盖」**，一眼可见哪里会丢分。任务引用了评分点清单之外的 id（AI 编造 / 想法插入未齐名）→ 单独「未识别引用」警示行。

前端数据源统一：任务卡评分点标注与覆盖总览共用 `plan.score_points`（落盘值），会话 `scorePoints` 仅作无落盘时的回退（理论上不会发生——拆解时同批写入）。

## 用户故事

1. 作为学生，我想要「题面每个评分点 → 覆盖它的任务」的反向视图，以便不用逐卡翻就能确认哪些评分点做了、哪些没做。
2. 作为学生，我想要「无任务覆盖的评分点」标红醒目，以便在交付前一眼看到丢分风险，并据此新想法补任务或修正任务评分点关联。
3. 作为学生，我想要任务引用了评分点清单外 id 时看到「未识别引用」警示，以便发现 AI 编造引用或清单被外部改动。
4. 作为学生，我想要评分点定义随清单落盘（刷新 / 历史目录不丢），以便离开当前会话仍然可以核对覆盖情况。
5. 作为学生，我想要任务卡的评分点标注在历史目录里也显示「基础/发挥 x 分」全信息（现在只有裸 id），以便卡上信息完整。

## 实现决策

- **数据模型**：`task_progress.py` 的 `TaskPlan` 增加字段 `score_points: tuple[Mapping[str, Any], ...] = ()`（存储 ScorePoint.to_dict() 形状：id/part/description/score/sentence_refs 原样透传）；`to_dict()` 序列化、`from_dict()` 读回——读回侧宽松：`score_points` 非列表 → 空；条目非 dict 或缺 id → 丢弃该条（不拒收整份清单，与既有「读回侧宁用默认态」哲学一致）。`TASKS_MANIFEST_VERSION` 保持 1（向后兼容读，无破坏性变更）。
- **落盘时机**：`run_task_planning` 构造 stamped `TaskPlan` 时写入入参 `score_points`（路由已传 `[p.to_dict() for p in score_points]`，webapp.py:2051）。旧清单（无字段）读回 = 空元组。
- **前端聚合（fx/task.js 纯函数）**：新增导出 `scoreRefsOverviewHTML(plan)`——空评分点 / 空清单 → `""`（容器隐藏）。聚合逻辑：遍历 `plan.score_points`，对每个点收集 `tasks[].score_refs` 中引用它的任务（保序）；行 = `id` + 分类中文标签（basic=基础 / development=发挥 / 其他，与 `taskScoreRefsText` 同判据）+ 分值 + description 截断（约 60 字，title 悬停全文）+ 覆盖任务列表（`tN：标题`，标题截断约 24 字）；无覆盖行加 `score-point-miss` class（红）与「⚠ 无任务覆盖」note；再扫一遍所有任务引用、不在已知评分点集合内的 id → 每 id 一行 `score-point-unknown`（黄）警示「未识别引用（不在评分点清单内）」+ 引用它的任务。
- **前端挂载**：`index.html` 在 `#tasks-resources` 之后新增容器 `#tasks-scorepoints`（同款 `class="hidden" style="margin-top:8px"`）；`ui/generate-tasks.js` `tasksRender` 中与 `resBox` 同模式渲染（`scoreBox.innerHTML = ...`；`classList.toggle("hidden", !html)`）。
- **前端数据源统一**：`tasksRender` 构造 `opts.scorePoints` 时改为 `scorePointsForPlan = (plan.score_points && plan.score_points.length) ? plan.score_points : scorePoints`（落盘优先、会话回退）——任务卡 `taskScoreRefsText` 与覆盖总览同源；历史目录任务卡标注自动补全分值信息。
- **样式**：`index.html` 新增 `.score-point-row`（行流布局，参照 `.res-row` 先例）、`.score-point-miss`（红：用 `var(--danger)` 语义，参照 `.res-conflict`）、`.score-point-unknown`（黄）、`.score-chip`（参照 `.res-chip`）、`.score-miss-note` / `.score-unknown-note`（小字注，参照 `.res-conflict-note` / `.res-soft-note`）。
- **纯函数约定**：fx 层不碰 DOM 状态、全部 esc 转义（description / title / id 均过 `esc`）；导出清单同步 `fx/task.js` 注释列表与 `tests/js/fx-guard.test.mjs`。

## 测试决策

- 后端（`tests/test_task_progress.py` 既有先例）：`TaskPlan` score_points 落盘 → 读回往返一致；`from_dict` 坏形状（非列表 / 条目非 dict / 缺 id / 部分坏条目混排）→ 宽松丢弃或空，不抛异常；旧契约 dict（无字段）→ score_points = ()。
- 前端（`tests/js/task.test.mjs` 既有先例，参考 `resourcesOverviewHTML` 测试写法）：
  - `scoreRefsOverviewHTML`：有覆盖 / 部分覆盖 / 全未覆盖的行结构与 class 断言；未知引用警示行；空评分点 / 空清单 / null → `""`；XSS 转义（`<img src=x>` title、description 带引号）；分类标签与分值格式（基础/发挥/其他）。
  - 任务卡同源：`taskCardHTML` 在 `opts.scorePoints` 为落盘值时的标注与 `taskScoreRefsText` 一致（历史目录场景：plan.score_points 非空、会话空 → 标注带全信息）。
- `fx-guard.test.mjs`：task.js 导出清单追加 `scoreRefsOverviewHTML`。
- 浏览器探针（已交付模式的 `.scratch/score-coverage/probe-score-coverage.mjs`，playwright）：容器可见性、未覆盖行红标、未知引用行、刷新后（重新 plan-read）视图仍在、截图确认视觉。
- 运行：`node --test "tests/js/*.test.mjs"` 全量 + `python -m pytest tests/test_task_progress.py` + 语言门禁 `tests/test_repo_language.py`。

## 范围外

- 未覆盖评分点的**自动补任务**（只警示，落地走既有「新想法」通道）。
- 评分点的增删改管理界面（改题面走重新推荐流程，不在本 spec）。
- 评分点权重 / 优先级的排序算法（按清单原序展示即可）。
- 多任务清单交叉统计（一个工程一份清单）。
- 用户先前提出的其它痛点：任务对话落盘、失败解释、开发记录导出、参数联动。
