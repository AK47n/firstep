# 逐步深化 | 做完一步自动提示「下一步」并定位下一张卡

## 问题陈述

用户实机使用任务推进时困惑：点「做这一步」执行的是**当前这一张卡**对应的单个步骤，执行完**不会**自动跳到下一张卡；同一张卡反复点「做这一步」/「重做」= 同一任务重做（每轮新实现 + 新备份）。用户原话：「我点做这一步是相当于在一直重做吗还是说在逐步推进」。根因：卡片只有「第 N 步（建议顺序）」序号，没有「下一步是哪张卡」的显式引导；执行成功后也没有把视线导向下一个待执行任务。

## 目标

执行一个任务成功后（SSE done），客户端自动：
1. **当前卡内**显示一行引导：「下一步 → t5：<标题>」（下一个待执行任务 = 当前卡之后、清单顺序上第一个 status ∈ {pending, failed} 的任务）；
2. **滚动 + 高亮**下一张卡（平滑滚到视口中央 + 2.4s 描边脉冲动画）；
3. 若无剩余待执行任务（其余都是 verified / unverified / doing / skipped）→ 不提示、不滚动。

不改变「做这一步 = 单卡执行、不自动执行下一步」的核心语义——自动定位只解决"不知道下一步在哪"，不替用户拍板。

## 用户故事

- 作为用户，我做完第 4 步后，当前卡上直接看到「下一步 → t5：标题」，不用自己找下一张卡；
- 页面自动滚到第 5 步那张卡并高亮它，我知道该点哪张；
- 当剩下的步骤全都处于"待上板/进行中/已跳过"时，不给我一个指向空处的「下一步」；
- 我反复点同一张卡的「做这一步」时，卡上不会出现"下一步是自己"这种误导提示。

## 实现决策

- **下一个待执行的口径**：清单顺序上在当前卡**之后**第一个 status ∈ {pending, failed} 的任务（建议顺序推进语义）；verified（编译绿闭环）/ unverified（待上板）/ doing（执行中）/ skipped（已跳过）都不算"下一步可执行"。找不到 → 返回空。
- **纯函数在 fx/task.js**（可单测、无 DOM）：
  - `nextTaskHint(plan, currentId)` → `{id, orderIndex, title} | null`（orderIndex 用于「第 N 步（建议顺序）」序号展示，取清单下标）；
  - `taskNextHintHTML(plan, currentId)` → 完整 HTML 串（`<div class="task-next-hint">下一步 → t5：<esc(title)></div>`）或空串；标题经 esc 防注入。
- **注入位置**：taskCardHTML 的卡容器是 `<div class="item" data-task-id="...">`（fx/task.js:70）；SSE done 后任务卡已由 tasksRender 整体重建，直接 `tasks-grid.querySelector('[data-task-id="<id>"]')` 定位当前卡，`insertAdjacentHTML("beforeend", hint)` 追加到操作行之后。提示是**瞬态**指引：下一次 grid 重渲染 / 重载后自然消失（可接受，不需要落盘）。
- **高亮**：下一张卡元素加类 `task-card-highlight`（CSS 动画 `task-next-glow` 2.4s：box-shadow 描边淡入淡出），2.6s 后移除类；`prefers-reduced-motion: reduce` 时禁用动画（保留滚动）。滚动用 `scrollIntoView({behavior:"smooth", block:"center"})`。
- **触发点**：ui/generate-tasks.js tasksExecute 的 SSE done 处理（`tasksRender` + `tasksRenderResult` 之后）——执行轮与上板反馈轮共用同一 done 路径，两者做完都引导下一步（反馈轮本质也是"这一张卡完成了一轮"）。
- **范围外**：自动执行下一个任务 / 任务队列 / 自动跳过 unverified / 修改「做这一步」按钮文案 / 任何后端改动（数据都在 plan 里，纯前端）。

## 测试决策

- `tests/js/task.test.mjs`：
  - `nextTaskHint`：命中当前卡后第一个 pending；跳过中间 verified/unverified/doing/skipped 命中后续 failed；全都不可执行 → null；当前卡不存在 / currentId 为空 → null；
  - `taskNextHintHTML`：标题含 `<`/`&` 转义；返回「下一步 → t5：」前缀 + 序号 = orderIndex+1；空 → "";
- `tests/js/fx-guard.test.mjs`：DOMAINS 登记 2 个新导出（nextTaskHint / taskNextHintHTML）；
- 探针（playwright，`.scratch/step-next-guide/`）：真实页面注入一张卡 + 提示行 + 高亮类，校验 CSS 类存在、`.task-next-hint` 渲染、`task-card-highlight` 动画类生效（glue 事件链由双轴 review 把关）；
- 全量 `node --test tests/js/*.test.mjs` 绿。

## 验收

- 做完一步：当前卡出现「下一步 → tN：标题」；下一张卡滚动到视口中央并高亮 ~2.4s；
- 无剩余待执行：无提示、无滚动；
- JS 全量测试绿；fx-guard 无漂移。
