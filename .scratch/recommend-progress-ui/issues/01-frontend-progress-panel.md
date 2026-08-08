# 01 — 推荐进度面板：轮次条 + 双计时器 + 卡死修复

**What to build:** 生成页第 3 步（AI 推荐模块）加进度面板：收敛轮次进度条 + 双计时器（总用时 / 当前轮已等待，每秒跳动），替代现状的"AI 收敛自检：第 N/4 轮…"一行文字；并修复 `/api/recommend` 的 400 与断线导致按钮永远卡在"AI 思考中…"的现状 bug。**纯前端改动，唯一文件 `src/contest_generator/static/index.html`，后端零改动**（round / converged 事件工单 10 已就绪，契约冻结不动）。

**Status:** resolved

**File boundary:** 只改 `src/contest_generator/static/index.html`。不得触碰 `src/contest_generator/`（sse.py / events.py / selection.py / webapp.py 及其测试）——契约与测试全绿即是对"没碰后端"的验证。

## 实现要点（已探明，直接照做）

**1. 面板 DOM**：第 3 步 card 内按钮 row 之后、`#recommend-msg` 之前插入：

```html
<div id="rec-progress" class="distill-progress hidden" style="margin-top:10px">
  <div id="rec-prog-text" style="margin-bottom:6px"></div>
  <div class="prog-bar hidden" id="rec-bar"><div id="rec-bar-fill"></div></div>
  <div class="prog-timers">
    <span id="rec-timer-total">总用时 00:00</span>
    <span id="rec-timer-round">当前轮已等待 00:00</span>
  </div>
</div>
```

CSS 类全部复用提炼面板现成的（`.distill-progress` / `.prog-bar` / `.prog-timers`，index.html:115-134），不新增样式。

**2. JS 状态机**（在"生成页：3. AI 推荐"区块内，`startRecommend` 附近）：

- `recProg` 对象：`{ startedAt, lastEventAt, timerId, finished }`，与提炼的 `prog`（index.html:1285-1443）同构但精简——无 stepper / 无日志 / 无批次。
- `startRecProgress()`：显示面板（`#rec-progress` 去 hidden、`#rec-bar` 加 hidden——首条 round 事件带 round_total 后再显示条）、`recProg` 置初值、`setInterval(tickRec, 1000)` 起跳；`tickRec()` 用全局 `fmtClock`（index.html:1331）刷新两个计时器：总用时 = now − startedAt，当前轮已等待 = now − lastEventAt。
- `stopRecProgress()`：clearInterval + 面板加 hidden。

**3. `startRecommend`（index.html:679-712）改造**：

- fetch 前调 `startRecProgress()`；`#rec-list` 不再写"AI 收敛自检中…"（状态文本进面板）。
- fetch 后查 `resp.ok`：不 OK → `const err = await resp.json().catch(() => ({})); showRecommendError(err.detail || ...)` 并 return（提炼端点同款，index.html:1527-1530）。
- SSE 回调：
  - `round` → `#rec-prog-text` = "AI 收敛自检：第 N/T 轮…"；`#rec-bar` 显示，`#rec-bar-fill` 宽度 = N/T × 100%；`recProg.lastEventAt = Date.now()`。
  - `converged` → 文本 = "功能需求层已收敛（第 N 轮）…"，条 100%（提前收敛跳满——round_total 是上限非保证）。
  - `done` → `recProg.finished = true; stopRecProgress();` 然后现有 `renderRecommendResult(ev)` + 按钮恢复。
  - `question` → `recProg.finished = true; stopRecProgress();` 然后现有 `showRecommendQuestions` + 按钮恢复（回答后 `startRecommend` 重启 = 新生命周期，面板从第 1 轮重新开始）。
  - `error` → `recProg.finished = true; stopRecProgress();` 然后现有 `showRecommendError`。
- 改成 `await parseSSE(resp, cb)`；结束后 `if (!recProg.finished) showRecommendError("连接中断：本次推荐未完成，可安全重试");`——断线 = 流结束无终态（提炼端点同款，index.html:1531-1534）。`showRecommendError`（index.html:660-664）已负责按钮恢复，复用即可。

**4. 不动**：按钮 spinner / disabled 行为、补问框、结果渲染（`renderRecommendResult`）、推荐端点后端、任何后端文件与测试。

## 验收清单

- [ ] 全量 pytest 绿 + mypy 绿（后端零改动，绿即验证）
- [ ] 自查（可选，工单 03 手法）：jsdom 载入整页 + 脚本化假流（`parseSSE` 纯函数，node 喂 `new Response(new ReadableStream(...))`）：round 推进（文本 + 条宽）、计时器跳动与事件后重置、converged 跳满、done 面板收起 + 结果渲染、question 面板收起 + 补问框、error 红字 + 按钮恢复、400（resp.ok false）红字 + 按钮恢复、断线提示 + 按钮恢复
- [ ] 真机验收：真实 API 跑 2021F 送药小车（第 2 轮收敛 → 条跳满、死寂期计时器跳动）；补问路径；断线（中途杀服务）；API 未配置 400

**Reference:** `.scratch/recommend-progress-ui/spec.md`、工单 10（`.scratch/contest-project-generator/issues/10-recommend-convergence.md`——事件契约出处）、工单 03 前端进度 UI（`.scratch/distill-progress/issues/03-frontend-progress-ui.md`——显示模式 / 存活证明 / 断线处理先例）、CONTEXT.md「进度事件」词条

## Comments

- 2026-08-08: grilling 会话（grill-with-docs + domain-modeling）产出，三项决策用户已拍板：① 前端 only（复用现有 round/converged 事件，不动 SSE 契约 + 测试）；② 面板形态 = 条 + 双计时器（无日志——推荐事件 ≤4 条无价值）；③ 卡死修复（resp.ok 检查 + 断线检测）同票并入。
- 2026-08-08: 已实现（worktree-recommend-progress-ui，唯一文件 index.html）。jsdom 整页载入 + 脚本化假流驱动 39 断言全绿：round 推进（文本 + 条宽 N/T）、双计时器每秒跳动 + 事件到达重置、converged 跳满、done 面板收起 + 结果照常渲染、question 面板收起 + 补问框 + 回答后从第 1 轮重来、error / 400（detail + 非 JSON 回退）/ 断线（EOF + 读流出错）红字提示 + 按钮恢复。全量 pytest 788 绿 + mypy 全绿（未碰任何后端文件）。真机验收待用户（2021F 送药小车第 2 轮收敛、补问路径、杀服务断线、API 未配置 400）。
