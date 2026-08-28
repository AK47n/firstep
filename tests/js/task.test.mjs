// task.test.mjs — fx/task.js 任务推进纯函数（工单 task-progress/01）：
// 状态徽章文案 / 验收方式标注 / 评分点引用 / 任务卡渲染 / 进度汇总 / 错误文案。
import test from "node:test";
import assert from "node:assert/strict";
import {
  taskStatusLabel, taskStatusBadgeClass, taskVerifyLabel,
  taskScoreRefsText, taskCardHTML, tasksGridHTML, tasksProgressText,
  tasksOverviewHTML, taskStepReportHTML, taskNextActionHTML,
  taskCardActions, verifyStatusMarkup,
  taskCanFeedback, taskIterationLabel, taskIterationsHTML, taskLatestFeedbackNote,
  taskOrderLabel, taskDialogAdoptHTML, taskDialogButtonHTML, taskDialogAreaHTML,
  nextTaskHint, taskNextHintHTML,
  ideaResultHTML, taskNeedsRedoBadge, taskStepReportBlocksHTML,
  globalChatHTML, globalNoteBadgeHTML,
  taskEditFormHTML, taskMoveButtonsHTML,
  ideaDraftListHTML,
} from "../../src/contest_generator/static/js/fx/task.js";

test("taskStatusLabel: 词表全覆盖", () => {
  assert.equal(taskStatusLabel("pending"), "待做");
  assert.equal(taskStatusLabel("doing"), "进行中");
  assert.equal(taskStatusLabel("verified"), "已验证");
  assert.equal(taskStatusLabel("unverified"), "未验证");
  assert.equal(taskStatusLabel("failed"), "失败");
  assert.equal(taskStatusLabel("skipped"), "已跳过");
  assert.equal(taskStatusLabel("bogus"), "未知");
});

test("taskStatusBadgeClass: 状态 → 徽章色", () => {
  assert.equal(taskStatusBadgeClass("verified"), "ok");
  assert.equal(taskStatusBadgeClass("failed"), "del");
  assert.equal(taskStatusBadgeClass("unverified"), "unverified");
  assert.equal(taskStatusBadgeClass("skipped"), "same");
  assert.equal(taskStatusBadgeClass("pending"), "out");
});

test("taskVerifyLabel: manual → 上板人工确认", () => {
  assert.equal(taskVerifyLabel("manual"), "需上板人工确认");
  assert.equal(taskVerifyLabel("compile"), "编译验证");
});

test("taskScoreRefsText: 评分点 id + 分值/部分标注", () => {
  const points = [
    { id: "s1", part: "basic", score: 20, description: "循迹" },
    { id: "s2", part: "development", score: null, description: "发挥" },
  ];
  const text = taskScoreRefsText(["s1", "s2"], points);
  assert.ok(text.includes("s1（基础 20 分）"));
  assert.ok(text.includes("s2（发挥）"));
  // 无评分点数据 → 只显示 id
  assert.equal(taskScoreRefsText(["s9"], []), "s9");
  // 空引用 → 空串
  assert.equal(taskScoreRefsText([], points), "");
});

test("taskCardHTML: 标题/描述/状态徽章/评分点/前置依赖/验收方式", () => {
  const html = taskCardHTML({
    id: "t1",
    title: "循迹决策",
    description: "根据灰度值控制电机",
    score_refs: ["s1"],
    depends_on: [],
    verify: "manual",
    status: "pending",
  }, 0, { scorePoints: [{ id: "s1", part: "basic", score: 20 }], actions: () => "<button>x</button>" });
  assert.ok(html.includes("t1 · 循迹决策"));
  assert.ok(html.includes("待做"));
  assert.ok(html.includes("循迹决策"));
  assert.ok(html.includes("s1（基础 20 分）"));
  assert.ok(html.includes("需上板人工确认"));
  assert.ok(html.includes("<button>x</button>"));
});

test("taskCardHTML: 前置依赖渲染", () => {
  const html = taskCardHTML({
    id: "t2", title: "显示", description: "显示结果",
    score_refs: [], depends_on: ["t1"], verify: "compile", status: "verified",
  }, 1, {});
  assert.ok(html.includes("前置：t1"));
  assert.ok(html.includes("已验证"));
});

test("tasksGridHTML: 空清单占位 + 多卡渲染", () => {
  assert.ok(tasksGridHTML({ tasks: [] }, {}).includes("任务清单为空"));
  const html = tasksGridHTML({ tasks: [
    { id: "t1", title: "A", description: "x", score_refs: [], depends_on: [], verify: "compile", status: "pending" },
    { id: "t2", title: "B", description: "y", score_refs: [], depends_on: ["t1"], verify: "compile", status: "skipped" },
  ] }, {});
  assert.ok(html.includes("t1 · A"));
  assert.ok(html.includes("已跳过"));
});

test("tasksProgressText: verified + skipped 计入完成", () => {
  assert.equal(tasksProgressText({ tasks: [
    { status: "verified" }, { status: "skipped" }, { status: "pending" },
  ] }), "进度 2/3");
  assert.equal(tasksProgressText({}), "进度 0/0");
});

test("verifyStatusMarkup: 三态徽章 + 摘要（深化/任务面板共用单源）", () => {
  const verified = verifyStatusMarkup({ status: "verified", compile: { exit_code: 0, summary: "0 errors" } }, {});
  assert.ok(verified.badge.includes("已验证"));
  assert.ok(verified.detail.includes("exit 0"));
  const unverified = verifyStatusMarkup({ status: "unverified", compile: {} }, { unverified: "任务自定义降级文案" });
  assert.ok(unverified.badge.includes("未验证"));
  assert.ok(unverified.detail.includes("任务自定义降级文案"));
  const failed = verifyStatusMarkup({ status: "failed" }, {});
  assert.ok(failed.badge.includes("未通过"));
  assert.ok(failed.detail.length > 0);
  // message 优先于 fallback（后端中文）
  const withMessage = verifyStatusMarkup({ status: "failed", message: "仍红的中文提示" }, {});
  assert.ok(withMessage.detail.includes("仍红的中文提示"));
});

test("taskCardActions: 显隐与后端转移表镜像", () => {
  // pending → 做这一步 + 跳过
  assert.deepEqual(taskCardActions("pending"), ["run", "skip"]);
  // skipped → 恢复；verified → 重做
  assert.deepEqual(taskCardActions("skipped"), ["revert"]);
  assert.deepEqual(taskCardActions("verified"), ["revert"]);
  // unverified / failed → 做 + 上板改标 + 重做
  assert.deepEqual(taskCardActions("unverified"), ["run", "mark", "revert"]);
  assert.deepEqual(taskCardActions("failed"), ["run", "mark", "revert"]);
  // doing → 无操作（执行中）
  assert.deepEqual(taskCardActions("doing"), []);
  // 未知状态 → 无操作（不猜）
  assert.deepEqual(taskCardActions("bogus"), []);
});

test("verifyStatusMarkup: unverified 按 cause 区分徽章（无工具链 / 手动验收）", () => {
  const noToolchain = verifyStatusMarkup({ status: "unverified", compile: {} }, {});
  assert.ok(noToolchain.badge.includes("无工具链降级"));
  const manual = verifyStatusMarkup({ status: "unverified", verify_cause: "manual", message: "请烧录观察后标记" }, {});
  assert.ok(manual.badge.includes("上板确认"));
  assert.ok(manual.detail.includes("请烧录观察后标记"));
});

// ---------------------------------------------------------------------------
// 上板反馈（工单 task-feedback/03）：反馈按钮显隐 / 轮次历史渲染
// ---------------------------------------------------------------------------

test("taskCanFeedback: 反馈按钮显隐矩阵（非 doing 且有产物或已终态）", () => {
  // 从未执行（无迭代）且待做 → 没有可观察产物，不显示
  assert.equal(taskCanFeedback({ status: "pending", iterations: [] }), false);
  // 执行过 → 可反馈（含回滚后的 pending——产物还在）
  assert.equal(taskCanFeedback({ status: "pending", iterations: [{ seq: 1 }] }), true);
  assert.equal(taskCanFeedback({ status: "verified", iterations: [{ seq: 1 }] }), true);
  assert.equal(taskCanFeedback({ status: "unverified", iterations: [{ seq: 1 }] }), true);
  assert.equal(taskCanFeedback({ status: "failed", iterations: [{ seq: 1 }] }), true);
  // 终态但无迭代记录（旧清单兼容）→ 也允许反馈
  assert.equal(taskCanFeedback({ status: "verified", iterations: [] }), true);
  assert.equal(taskCanFeedback({ status: "unverified", iterations: [] }), true);
  // 执行中 → 禁止
  assert.equal(taskCanFeedback({ status: "doing", iterations: [] }), false);
});

test("taskIterationLabel: 轮次种类标签", () => {
  assert.equal(taskIterationLabel("execute"), "初始执行");
  assert.equal(taskIterationLabel("feedback"), "上板反馈");
  assert.equal(taskIterationLabel("bogus"), "执行");
});

test("taskIterationsHTML: 空历史 → 空串；有记录 → 轮次行 + 回滚按钮", () => {
  assert.equal(taskIterationsHTML({ iterations: [] }), "");
  const html = taskIterationsHTML({
    id: "t1",
    iterations: [
      { seq: 1, kind: "execute", feedback: "", status: "verified", backup_id: "b1", at: "2026-08-27T10:00:00+0800", compile_summary: "Build succeeded (0 error)" },
      { seq: 2, kind: "feedback", feedback: "左轮不转，向右偏", status: "unverified", backup_id: "b2", at: "2026-08-27T11:00:00+0800", compile_summary: "" },
    ],
  });
  assert.ok(html.includes("第 1 轮"));
  assert.ok(html.includes("初始执行"));
  assert.ok(html.includes("第 2 轮"));
  assert.ok(html.includes("上板反馈"));
  assert.ok(html.includes("左轮不转"));
  assert.ok(html.includes("data-seq=\"2\""));
  // 时间 + 编译结果徽章（评审 (a)：at / compile_summary 落盘必须有 UI 出口）
  assert.ok(html.includes("2026-08-27T10:00:00+0800"));
  assert.ok(html.includes("编译：Build succeeded"));
  assert.ok(html.includes("2026-08-27T11:00:00+0800"));
  // 编译徽章颜色按该轮终态推断：verified → ok
  assert.ok(html.includes("badge ok\">编译："));
  // 无备份的轮次不给回滚按钮（防御：历史记录里可能有空 backup_id）
  const noBackup = taskIterationsHTML({
    id: "t1",
    iterations: [{ seq: 3, kind: "execute", feedback: "", status: "failed", backup_id: "", at: "" }],
  });
  assert.ok(!noBackup.includes("data-seq=\"3\""));
});

test("taskLatestFeedbackNote: 最近一轮是上板反馈 → 原文回溯；否则空串", () => {
  assert.equal(taskLatestFeedbackNote({ iterations: [] }), "");
  assert.equal(taskLatestFeedbackNote({}), "");
  assert.equal(taskLatestFeedbackNote({ iterations: [{ kind: "execute", feedback: "x" }] }), "");
  assert.equal(taskLatestFeedbackNote({ iterations: [{ kind: "feedback", feedback: "" }] }), "");
  const html = taskLatestFeedbackNote({
    iterations: [{ kind: "execute", feedback: "" }, { kind: "feedback", feedback: "上板发现左轮不转" }],
  });
  assert.ok(html.includes("上板反馈"));
  assert.ok(html.includes("上板发现左轮不转"));
});

test("taskCardHTML: 卡内渲染轮次历史（有记录追加，无记录不变）", () => {
  const base = taskCardHTML({
    id: "t1", title: "循迹", description: "决策",
    score_refs: [], depends_on: [], verify: "compile", status: "verified",
  }, 0, {});
  assert.ok(!base.includes("历史记录"));
  const withHistory = taskCardHTML({
    id: "t1", title: "循迹", description: "决策",
    score_refs: [], depends_on: [], verify: "compile", status: "verified",
    iterations: [{ seq: 1, kind: "execute", feedback: "", status: "verified", backup_id: "b1", at: "2026-08-27T10:00:00+0800" }],
  }, 0, {});
  assert.ok(withHistory.includes("历史记录"));
  assert.ok(withHistory.includes("第 1 轮"));
});

// ---------------------------------------------------------------------------
// 任务序号 + 每卡对话区（工单 task-chat/03）
// ---------------------------------------------------------------------------

test("taskOrderLabel: index 0 起 → 「第 N 步（建议顺序）」", () => {
  assert.equal(taskOrderLabel(0), "第 1 步（建议顺序）");
  assert.equal(taskOrderLabel(2), "第 3 步（建议顺序）");
});

test("taskCardHTML: 序号进标题行（第 N 步（建议顺序）· t1 · 标题）", () => {
  const html = taskCardHTML({
    id: "t1", title: "循迹决策", description: "根据灰度值控制电机",
    score_refs: [], depends_on: [], verify: "compile", status: "pending",
  }, 0, {});
  assert.ok(html.includes("第 1 步（建议顺序） · t1 · 循迹决策"));
});

test("tasksGridHTML: 建议顺序声明行（不强制，可跳着做）", () => {
  const html = tasksGridHTML({ tasks: [
    { id: "t1", title: "A", description: "x", score_refs: [], depends_on: [], verify: "compile", status: "pending" },
  ] }, {});
  assert.ok(html.includes("建议按序号从上往下做"));
  assert.ok(html.includes("不强制，可跳着做"));
});

test("taskDialogAdoptHTML: 未采纳 → 空串；已采纳 → 徽标 + 摘要 + 取消按钮", () => {
  assert.equal(taskDialogAdoptHTML({ dialog_note: "" }), "");
  assert.equal(taskDialogAdoptHTML({}), "");
  const html = taskDialogAdoptHTML({ id: "t1", dialog_note: "左轮不转：改为脉冲式控制" });
  assert.ok(html.includes("已采纳对话结论"));
  assert.ok(html.includes("左轮不转：改为脉冲式控制"));
  assert.ok(html.includes("btn-task-dialog-clear"));
  assert.ok(html.includes("data-task=\"t1\""));
  // 超长摘要截 30 字
  const long = taskDialogAdoptHTML({ id: "t1", dialog_note: "x".repeat(50) });
  assert.ok(long.includes("…"));
});

test("taskDialogButtonHTML: doing 不显示；open 切换文案（工单 06 文案澄清）", () => {
  assert.equal(taskDialogButtonHTML({ id: "t1", status: "doing" }, null), "");
  const closed = taskDialogButtonHTML({ id: "t1", status: "pending" }, { open: false });
  assert.ok(closed.includes("有不懂的？问这里"));
  assert.ok(closed.includes("data-task=\"t1\""));
  const open = taskDialogButtonHTML({ id: "t1", status: "verified" }, { open: true });
  assert.ok(open.includes("收起讨论"));
});

test("taskDialogAreaHTML: 未展开 → 空串；展开空历史 → 澄清引导语；有历史 → 消息 + 采纳按钮", () => {
  assert.equal(taskDialogAreaHTML({ id: "t1" }, { open: false }), "");
  const empty = taskDialogAreaHTML({ id: "t1" }, { open: true, history: [], busy: false });
  assert.ok(empty.includes("这一步有不懂或想确认的地方"));
  assert.ok(empty.includes("task-dialog-input-t1"));
  const st = {
    open: true, busy: false,
    history: [
      { role: "user", content: "左轮不转" },
      { role: "assistant", content: "建议改成脉冲式，GPIO 复用方向位即可。" },
    ],
  };
  const html = taskDialogAreaHTML({ id: "t1" }, st);
  assert.ok(html.includes('<span class="sugg-msg-role">我</span>：'));
  assert.ok(html.includes("左轮不转"));
  assert.ok(html.includes('<span class="sugg-msg-role">AI</span>：'));
  assert.ok(html.includes("建议改成脉冲式"));
  assert.ok(html.includes("采纳这条结论"));
  assert.ok(html.includes("data-task-adopt=\"t1\""));
  assert.ok(html.includes("data-idx=\"1\""));
  // AI 行才有采纳按钮（user 行不带）
  assert.ok(!html.includes("data-idx=\"0\""));
  // busy 提示 + 发送禁用
  const busy = taskDialogAreaHTML({ id: "t1" }, { open: true, busy: true, history: [{ role: "user", content: "x" }] });
  assert.ok(busy.includes("AI 回应中"));
  assert.ok(busy.includes("disabled"));
});

// ---------------------------------------------------------------------------
// 逐步深化（工单 stepwise-deepen/02）：进度总览 / 步骤报告 / 卡片「下一步要做」
// ---------------------------------------------------------------------------

test("tasksOverviewHTML: 分段进度条 + 状态汇总（已跳过单列不计完成）", () => {
  const plan = { tasks: [
    { id: "t1", status: "verified" },
    { id: "t2", status: "verified" },
    { id: "t3", status: "unverified" },
    { id: "t4", status: "failed" },
    { id: "t5", status: "doing" },
    { id: "t6", status: "pending" },
    { id: "t7", status: "skipped" },
  ] };
  const html = tasksOverviewHTML(plan);
  assert.ok(html.includes("已完成 <b style=\"color:var(--ok-bright)\">2</b>/7"));
  assert.ok(html.includes("待上板 1"));
  assert.ok(html.includes("失败 1"));
  assert.ok(html.includes("进行中 1"));
  assert.ok(html.includes("待做 1"));
  assert.ok(html.includes("已跳过 1（不计入完成）"));
  assert.ok(html.includes("seg-ok"));
  assert.ok(html.includes("seg-unverified"));
  assert.ok(html.includes("seg-failed"));
  assert.ok(html.includes("seg-skipped"));
  // 空清单 → 空串（前端容器隐藏）
  assert.equal(tasksOverviewHTML({ tasks: [] }), "");
  assert.equal(tasksOverviewHTML(null), "");
});

test("taskStepReportHTML: 最新一轮报告两块渲染 + 降级兜底", () => {
  const task = { id: "t1", title: "循迹", status: "unverified", iterations: [
    { seq: 1, kind: "execute", status: "unverified", what_changed: "实现了循迹状态机与灰度阈值判定", user_action: "把 PA0 接到灰度循迹模块 DIO，烧录后观察小车是否沿线" },
  ] };
  const html = taskStepReportHTML(task);
  assert.ok(html.includes("步骤报告"));
  assert.ok(html.includes("AI 做了什么："));
  assert.ok(html.includes("实现了循迹状态机"));
  assert.ok(html.includes("接下来你要做什么："));
  assert.ok(html.includes("PA0 接到灰度循迹模块 DIO"));
  // 报告调用降级（两字段空串）→ 中文兜底文案（中性：空结果 ≠ 必然降级）
  const degraded = taskStepReportHTML({ id: "t1", iterations: [{ seq: 1, kind: "execute", status: "verified", what_changed: "", user_action: "" }] });
  assert.ok(degraded.includes("本步说明为空"));
  assert.ok(degraded.includes("本步无需额外人工动作"));
  // 无轮次 → 空串（未执行过无报告）
  assert.equal(taskStepReportHTML({ id: "t1", iterations: [] }), "");
  assert.equal(taskStepReportHTML(null), "");
});

test("taskNextActionHTML: 未上板/编译通过待上板显示「下一步要做」；人工已确认/执行中/无指引 = 空串", () => {
  const iter = [{ seq: 1, kind: "execute", status: "unverified", user_action: "把 PB1 接到步进模块 DIR" }];
  const html = taskNextActionHTML({ id: "t1", status: "unverified", iterations: iter });
  assert.ok(html.includes("下一步要做"));
  assert.ok(html.includes("PB1 接到步进模块 DIR"));
  // compile 任务 verified = 仅编译通过，仍需烧录上板 → 指引常驻（工单 04 修正：
  // 旧实现 verified 一律隐藏，用户实测看不到「该怎么做上板」）
  const compileOk = taskNextActionHTML({ id: "t1", verify: "compile", status: "verified", iterations: iter });
  assert.ok(compileOk.includes("下一步要做"));
  assert.ok(compileOk.includes("PB1 接到步进模块 DIR"));
  // manual 任务 verified = 用户已上板人工确认 → 空串（该步已闭环）
  assert.equal(taskNextActionHTML({ id: "t1", verify: "manual", status: "verified", iterations: iter }), "");
  // 执行中 → 空串（旧指引不代表当前轮）
  assert.equal(taskNextActionHTML({ id: "t1", status: "doing", iterations: iter }), "");
  // 无 user_action（降级）/ 无轮次 → 空串
  assert.equal(taskNextActionHTML({ id: "t1", status: "unverified", iterations: [{ seq: 1, status: "unverified", user_action: "" }] }), "");
  assert.equal(taskNextActionHTML({ id: "t1", status: "pending", iterations: [] }), "");
});

test("taskCardHTML: 下一步要做摘要进卡（有则渲染，无则卡形不变）", () => {
  const base = taskCardHTML({
    id: "t1", title: "寻迹", description: "x", score_refs: [], depends_on: [],
    verify: "manual", status: "unverified",
    iterations: [{ seq: 1, kind: "execute", status: "unverified", user_action: "烧录后观察循迹效果" }],
  }, 0, {});
  assert.ok(base.includes("下一步要做"));
  assert.ok(base.includes("烧录后观察循迹效果"));
  // 未上板（unverified）卡上明示「待上板」（spec：总览与卡片都标注）
  assert.ok(base.includes("待上板"));
  const verified = taskCardHTML({
    id: "t1", title: "寻迹", description: "x", score_refs: [], depends_on: [],
    verify: "manual", status: "verified", iterations: [],
  }, 0, {});
  assert.ok(!verified.includes("待上板"));
  // compile 任务已验证（编译绿）→ 卡上仍显示上板指引（工单 04：编译通过 ≠ 上板完成）
  const compileOk = taskCardHTML({
    id: "t1", title: "寻迹", description: "x", score_refs: [], depends_on: [],
    verify: "compile", status: "verified",
    iterations: [{ seq: 1, kind: "execute", status: "verified", user_action: "烧录后观察循迹效果" }],
  }, 0, {});
  assert.ok(compileOk.includes("下一步要做"));
  assert.ok(compileOk.includes("烧录后观察循迹效果"));
  const plain = taskCardHTML({
    id: "t1", title: "寻迹", description: "x", score_refs: [], depends_on: [],
    verify: "compile", status: "pending", iterations: [],
  }, 0, {});
  assert.ok(!plain.includes("下一步要做"));
});

test("taskCardHTML: 卡内烧录控制行（outputDir + 已实现步骤显；pending/doing/无目录隐）", () => {
  const hasRun = {
    id: "t1", title: "寻迹", description: "x", score_refs: [], depends_on: [],
    verify: "compile", status: "verified",
    iterations: [{ seq: 1, kind: "execute", status: "verified" }],
  };
  // 已终态（无迭代记录也允许——旧清单终态任务，taskCanFeedback 判据）
  const terminal = {
    id: "t2", title: "显示", description: "x", score_refs: [], depends_on: [],
    verify: "compile", status: "unverified", iterations: [],
  };
  const withDir = taskCardHTML(hasRun, 0, { outputDir: "C:/proj" });
  assert.ok(withDir.includes('id="tasks-flash-status-t1"'));
  assert.ok(withDir.includes('id="tasks-flash-result-t1"'));
  assert.ok(withDir.includes("烧录到板子"));
  assert.ok(withDir.includes('data-task-flash="t1"'));
  const terminalCard = taskCardHTML(terminal, 1, { outputDir: "C:/proj" });
  assert.ok(terminalCard.includes('id="tasks-flash-status-t2"'));
  // 未实现（pending）/ 执行中（doing）/ 无目录 → 不显示（防烧旧固件 / 防并发）
  const pending = taskCardHTML({
    id: "t9", title: "T", description: "x", score_refs: [], depends_on: [],
    verify: "compile", status: "pending", iterations: [],
  }, 0, { outputDir: "C:/proj" });
  assert.ok(!pending.includes("tasks-flash-status-t9"));
  const doing = taskCardHTML({
    id: "t8", title: "T", description: "x", score_refs: [], depends_on: [],
    verify: "compile", status: "doing", iterations: [],
  }, 0, { outputDir: "C:/proj" });
  assert.ok(!doing.includes("tasks-flash-status-t8"));
  const noDir = taskCardHTML(hasRun, 0, {});
  assert.ok(!noDir.includes("tasks-flash-status-t1"));
});

test("taskIterationsHTML: 轮次行带「做了什么」摘要（截 40 字）", () => {
  const task = { id: "t1", iterations: [
    { seq: 1, kind: "execute", status: "verified", compile_summary: "ok", what_changed: "x".repeat(50) },
  ] };
  const html = taskIterationsHTML(task);
  assert.ok(html.includes("x".repeat(40) + "…"));
  // 降级空字段 → 无摘要块
  const noReport = taskIterationsHTML({ id: "t1", iterations: [
    { seq: 1, kind: "execute", status: "verified", compile_summary: "ok" },
  ] });
  assert.ok(noReport.includes("第 1 轮"));
  assert.ok(!noReport.includes("「"));
});

test("nextTaskHint: 当前卡之后第一个待执行（pending/failed）", () => {
  const plan = { tasks: [
    { id: "t1", title: "一", status: "verified" },
    { id: "t2", title: "二", status: "unverified" },
    { id: "t3", title: "三", status: "pending" },
    { id: "t4", title: "四", status: "failed" },
    { id: "t5", title: "五", status: "pending" },
  ] };
  // 命中 t3（跳过已验证/待上板）
  assert.deepEqual(nextTaskHint(plan, "t1"), { id: "t3", orderIndex: 2, title: "三" });
  // 命中 t4（跳过 pending 之前的状态）
  assert.deepEqual(nextTaskHint(plan, "t3"), { id: "t4", orderIndex: 3, title: "四" });
  // 之后无待执行 → null
  assert.equal(nextTaskHint(plan, "t5"), null);
  // 当前卡不存在 / 空 plan / 空 currentId → null
  assert.equal(nextTaskHint(plan, "t99"), null);
  assert.equal(nextTaskHint({ tasks: [] }, "t1"), null);
  assert.equal(nextTaskHint(plan, ""), null);
  assert.equal(nextTaskHint(null, "t1"), null);
  // doing / skipped 不算待执行
  const doingAfter = { tasks: [
    { id: "t1", title: "一", status: "doing" },
    { id: "t2", title: "二", status: "skipped" },
    { id: "t3", title: "三", status: "pending" },
  ] };
  assert.deepEqual(nextTaskHint(doingAfter, "t1"), { id: "t3", orderIndex: 2, title: "三" });
  // 当前卡之后全为不可执行（verified/unverified/doing/skipped）→ null
  const noneExecutable = { tasks: [
    { id: "t1", title: "一", status: "pending" },
    { id: "t2", title: "二", status: "verified" },
    { id: "t3", title: "三", status: "unverified" },
    { id: "t4", title: "四", status: "skipped" },
  ] };
  assert.equal(nextTaskHint(noneExecutable, "t1"), null);
});

test("taskNextHintHTML: 下一步提示行（转义 + 序号 + 空串）", () => {
  const plan = { tasks: [
    { id: "t1", title: "一", status: "verified" },
    { id: "t4", title: "A到B <直线> & 停车", status: "pending" },
  ] };
  const html = taskNextHintHTML(plan, "t1");
  assert.ok(html.includes("task-next-hint"));
  assert.ok(html.includes("下一步 → t4："));
  assert.ok(html.includes("A到B &lt;直线&gt; &amp; 停车"));  // esc 转义
  assert.ok(!html.includes("<直线>"));
  // 无下一步 → 空串
  assert.equal(taskNextHintHTML(plan, "t4"), "");
  assert.equal(taskNextHintHTML({ tasks: [] }, "t1"), "");
});

test("ideaResultHTML: 三种分类结果卡（徽章 + 落地按钮区）", () => {
  // new_task → 「生成任务」按钮 + 建议任务预览（标题/描述/依赖序号）
  const nt = ideaResultHTML({
    kind: "new_task",
    reply: "这是清单里没有的新功能：进弯道前减速。",
    new_task: { title: "弯道减速", description: "检测弯道后降低速度", depends_on: [1] },
    fix_summary: "",
    affected_task_ids: [],
  }, {});
  assert.ok(nt.includes("新功能任务"));
  assert.ok(nt.includes("进弯道前减速"));
  assert.ok(nt.includes("弯道减速"));
  assert.ok(nt.includes("依赖：第 1 步"));
  assert.ok(nt.includes("btn-idea-insert"));
  assert.ok(nt.includes("生成任务"));
  assert.ok(!nt.includes("btn-idea-fix"));
  // direct_fix → 「改动预览并执行」按钮 + 修正建议 + 受影响任务
  const df = ideaResultHTML({
    kind: "direct_fix",
    reply: "阈值太高，直接改。",
    new_task: null,
    fix_summary: "把阈值从 500 降到 350",
    affected_task_ids: ["t1", "t2"],
  }, {});
  assert.ok(df.includes("改现有代码"));
  assert.ok(df.includes("把阈值从 500 降到 350"));
  assert.ok(df.includes("受影响任务"));
  assert.ok(df.includes("t1、t2"));
  assert.ok(df.includes("btn-idea-fix"));
  assert.ok(df.includes("改动预览并执行"));
  assert.ok(!df.includes("btn-idea-insert"));
  // discussion → 两个转换按钮（漏斗态）
  const dc = ideaResultHTML({
    kind: "discussion", reply: "这个想法值得先聊聊。", new_task: null,
    fix_summary: "", affected_task_ids: [],
  }, {});
  assert.ok(dc.includes("先讨论"));
  assert.ok(dc.includes("btn-idea-to-task"));
  assert.ok(dc.includes("把建议变成任务"));
  assert.ok(dc.includes("btn-idea-to-fix"));
  assert.ok(dc.includes("把建议变成修正"));
  assert.ok(!dc.includes("btn-idea-insert"));
});

test("ideaResultHTML: 落地后 landedNote 替换按钮区 + 转义", () => {
  const landed = ideaResultHTML({
    kind: "new_task",
    reply: "建议加一个功能。",
    new_task: { title: "弯道减速", description: "描述" },
  }, { landedNote: "已生成任务卡——可点「做这一步」执行" });
  assert.ok(landed.includes("已生成任务卡"));
  assert.ok(!landed.includes("btn-idea-insert"));
  // reply 转义（防注入）
  const escaped = ideaResultHTML({
    kind: "discussion", reply: "<script>alert(1)</script> & 建议",
  }, {});
  assert.ok(escaped.includes("&lt;script&gt;"));
  assert.ok(!escaped.includes("<script>alert(1)"));
});

test("ideaResultHTML: opts.idea 回显用户原文（故事 6）", () => {
  const html = ideaResultHTML({
    kind: "direct_fix", reply: "阈值太高，直接改。",
    fix_summary: "把阈值从 500 降到 350",
  }, { idea: "循迹阈值太高" });
  assert.ok(html.includes("你的想法"));
  assert.ok(html.includes("循迹阈值太高"));
  // 无 idea → 不回显
  const plain = ideaResultHTML({ kind: "direct_fix", reply: "好。" }, {});
  assert.ok(!plain.includes("你的想法"));
});

test("taskStepReportBlocksHTML: 两块正文共享单源（结果面板共用）", () => {
  const html = taskStepReportBlocksHTML("实现了循迹状态机。", "把 PA0 接到灰度 DIO。");
  assert.ok(html.includes("AI 做了什么"));
  assert.ok(html.includes("实现了循迹状态机。"));
  assert.ok(html.includes("接下来你要做什么"));
  assert.ok(html.includes("把 PA0 接到灰度 DIO。"));
  // 空值 → 中文兜底
  const fallback = taskStepReportBlocksHTML("", "");
  assert.ok(fallback.includes("本步说明为空"));
  assert.ok(fallback.includes("无需额外人工动作"));
});

test("taskNeedsRedoBadge: 建议重做徽章显隐", () => {
  assert.ok(taskNeedsRedoBadge({ id: "t1", needs_redo: true }).includes("⚠ 建议重做"));
  assert.equal(taskNeedsRedoBadge({ id: "t1", needs_redo: false }), "");
  assert.equal(taskNeedsRedoBadge({ id: "t1" }), "");
  assert.equal(taskNeedsRedoBadge(null), "");
});

test("taskCardHTML: needs_redo 集成徽章（卡头）", () => {
  const html = taskCardHTML({
    id: "t1", title: "循迹", description: "循迹决策", score_refs: [],
    depends_on: [], verify: "compile", status: "verified", needs_redo: true,
  }, 0, {});
  assert.ok(html.includes("⚠ 建议重做"));
  // 未标记 → 无徽章
  const clean = taskCardHTML({
    id: "t2", title: "显示", description: "显示", score_refs: [],
    depends_on: [], verify: "compile", status: "verified", needs_redo: false,
  }, 1, {});
  assert.ok(!clean.includes("建议重做"));
});

test("globalChatHTML: 未展开 → 空串；空历史 → 引导文案 + 输入行", () => {
  const st = { open: true, chat: { messages: [], note: "" }, busy: false };
  const html = globalChatHTML(st);
  assert.ok(html.includes("task-dialog-box"));
  assert.ok(html.includes("针对整个工程的问题区"));
  assert.ok(html.includes('id="tasks-global-chat-input"'));
  assert.ok(html.includes("发送"));
  // 未展开 → 空串
  assert.equal(globalChatHTML({ open: false }), "");
});

test("globalChatHTML: 历史分行 + AI 回复三按钮（data 属性转义）", () => {
  const st = {
    open: true, busy: true,
    chat: {
      messages: [
        { role: "user", content: "整体架构要不要加滤波？", at: "2026-01-01T00:00:00" },
        { role: "assistant", content: '建议加一阶低通——"阈值" 500。', at: "2026-01-01T00:00:05" },
      ],
      note: "",
    },
    pending: "",
  };
  const html = globalChatHTML(st);
  // 用户行无按钮；AI 行有三按钮
  assert.ok(html.includes('class="sugg-msg user"'));
  assert.ok(html.includes('data-global-action="task"'));
  assert.ok(html.includes('data-global-action="fix"'));
  assert.ok(html.includes('data-global-action="adopt"'));
  // data-global-text 转义：引号 → &quot;（属性上下文防注入；浏览器读回
  // dataset 时解码回原引号——往返成立）
  assert.ok(html.includes('data-global-text="建议加一阶低通——&quot;阈值&quot; 500。"'));
  assert.ok(html.includes("sugg-msg-role\">AI</span>"));
  // busy 输入禁用
  assert.ok(html.includes("disabled"));
  assert.ok(html.includes("回应中…"));
});

test("globalChatHTML: pending 乐观展示待确认用户消息", () => {
  const st = {
    open: true, busy: true,
    chat: { messages: [], note: "" },
    pending: "还没说的消息",
  };
  const html = globalChatHTML(st);
  assert.ok(html.includes("还没说的消息"));
  assert.ok(html.includes('class="sugg-msg user"'));
});

test("globalChatHTML: AI 回复文本注入转义（不再拼裸文本）", () => {
  const st = {
    open: true,
    chat: { messages: [{ role: "assistant", content: "<script>alert(1)</script>" }], note: "" },
  };
  const html = globalChatHTML(st);
  assert.ok(!html.includes("<script>alert(1)</script>"));
  assert.ok(html.includes("&lt;script&gt;alert(1)&lt;/script&gt;"));
});

test("globalNoteBadgeHTML: 空 → 空串；非空 → 徽标 + 摘要 30 字 + 清除按钮", () => {
  assert.equal(globalNoteBadgeHTML(""), "");
  assert.equal(globalNoteBadgeHTML("   "), "");
  assert.equal(globalNoteBadgeHTML(null), "");
  const note = "全局结论：先保证循迹稳定再上 PID（这次比赛以稳定优先）——这句话超过三十个字了吗？";
  const html = globalNoteBadgeHTML(note);
  assert.ok(html.includes("工程级全局结论"));
  assert.ok(html.includes('data-global-action="clear"'));
  assert.ok(html.includes("清除"));
  // 摘要截 30 字 + 「…」（完整全文在 title 提示里，可见文本带省略号）
  assert.ok(html.includes(note.slice(0, 30) + "…"));
  assert.ok(html.includes("title="));
  // 短 note 全文显示 + 转义
  const short = globalNoteBadgeHTML('<b>阈值 500</b>');
  assert.ok(short.includes("&lt;b&gt;阈值 500&lt;/b&gt;"));
  assert.ok(!short.includes("<b>阈值 500</b>"));
});

test("taskMoveButtonsHTML: ↑/↓ + 边界禁用 + data 属性", () => {
  const first = taskMoveButtonsHTML({ id: "t1" }, 0, 2);
  assert.ok(first.includes('data-task-action="move-up"'));
  assert.ok(first.includes('data-task-action="move-down"'));
  assert.ok(first.includes('data-task="t1"'));
  assert.ok(first.includes("move-up\" data-task=\"t1\" disabled"));  // 首卡 ↑ 禁用
  assert.ok(!first.includes("move-down\" data-task=\"t1\" disabled"));  // 末卡 ↓ 不禁用（t1 不是末卡）
  const last = taskMoveButtonsHTML({ id: "t2" }, 1, 2);
  assert.ok(last.includes("move-down\" data-task=\"t2\" disabled"));
  assert.ok(!last.includes("move-up\" data-task=\"t2\" disabled"));
  // id 转义
  const weird = taskMoveButtonsHTML({ id: 't"x' }, 0, 1);
  assert.ok(weird.includes('data-task="t&quot;x"'));
});

test("taskEditFormHTML: 当前值回填（依赖序号经 seqById 转换）+ 保存/取消按钮", () => {
  const task = {
    id: "t2",
    title: 'OLED <b>显示</b>',
    description: "显示分值",
    depends_on: ["t1"],
    verify: "manual",
    score_refs: ["s1", "s2"],
  };
  const html = taskEditFormHTML(task, { seqById: { t1: 1 } });
  // 值回填 + 转义（值进属性/文本一律 esc）
  assert.ok(html.includes('id="task-edit-title-t2" value="OLED &lt;b&gt;显示&lt;/b&gt;"'));
  assert.ok(html.includes("task-edit-desc-t2"));
  assert.ok(html.includes('value="1"'));                 // 依赖 t1 → 序号 1
  assert.ok(html.includes('value="manual" selected'));   // 验收方式选中
  assert.ok(html.includes('value="compile"'));
  assert.ok(html.includes('value="s1, s2"'));            // 评分点回填
  assert.ok(html.includes('data-task-action="edit-save" data-task="t2"'));
  assert.ok(html.includes('data-task-action="edit-cancel" data-task="t2"'));
  // 无依赖 / compile / 空评分点
  const empty = taskEditFormHTML({ id: "t1", title: "循迹", description: "循迹决策", depends_on: [], verify: "compile", score_refs: [] }, { seqById: {} });
  assert.ok(empty.includes('id="task-edit-deps-t1" value=""'));
  assert.ok(empty.includes('value="compile" selected'));
  assert.ok(empty.includes('id="task-edit-refs-t1" value=""'));
});

test("taskCardHTML: 编辑按钮 + ↑/↓ 集成；editing 态渲染表单", () => {
  const task = {
    id: "t1", title: "循迹", description: "循迹决策", score_refs: [],
    depends_on: [], verify: "compile", status: "pending", iterations: [],
  };
  const card = taskCardHTML(task, 0, { total: 2, editing: () => false });
  assert.ok(card.includes('class="btn-task-edit"'));
  assert.ok(card.includes('data-task-action="edit" data-task="t1"'));
  assert.ok(card.includes('class="task-move"'));
  assert.ok(card.includes("move-up\" data-task=\"t1\" disabled"));
  assert.ok(!card.includes("task-edit-title-"));  // 未展开无表单
  const editing = taskCardHTML(task, 0, { total: 2, editing: () => true });
  assert.ok(editing.includes("task-edit-title-t1"));
  assert.ok(editing.includes("data-task-action=\"edit-save\""));
});

test("ideaDraftListHTML: 空列表 → 引导文案；非空 → 条目 + 分析/删除/全部按钮", () => {
  const empty = ideaDraftListHTML([], {});
  assert.ok(empty.includes("暂无草稿"));
  assert.ok(!empty.includes("data-draft-action"));
  const drafts = [{ id: "a1", text: "循迹阈值太高", at: "" }, { id: "a2", text: "进弯道前先减速", at: "" }];
  const html = ideaDraftListHTML(drafts, {});
  assert.ok(html.includes("草稿（2 条）"));
  assert.ok(html.includes('data-draft-action="analyze"'));
  assert.ok(html.includes('data-draft-action="delete"'));
  assert.ok(html.includes('data-draft-action="all"'));
  assert.ok(html.includes('data-draft-text="循迹阈值太高"'));
  assert.ok(html.includes('data-draft-id="a2"'));
  // 长文本截 60 字 + title 全文
  const long = "长".repeat(80);
  const longHtml = ideaDraftListHTML([{ id: "a1", text: long, at: "" }], {});
  assert.ok(longHtml.includes('title="' + long + '"'));
  assert.ok(longHtml.includes("长".repeat(60) + "…"));
});

test("ideaDraftListHTML: busy 禁用全部按钮 + 注入转义", () => {
  const busy = ideaDraftListHTML([{ id: "a1", text: "x", at: "" }], { busy: true });
  assert.ok(busy.includes('data-draft-action="analyze" data-draft-text="x" disabled'));
  assert.ok(busy.includes('data-draft-action="delete" data-draft-id="a1" disabled'));
  assert.ok(busy.includes('data-draft-action="all" disabled'));
  const evil = ideaDraftListHTML([{ id: 'd"1', text: '<script>alert(1)</script>', at: "" }], {});
  assert.ok(!evil.includes("<script>alert(1)</script>"));
  assert.ok(evil.includes("&lt;script&gt;alert(1)&lt;/script&gt;"));
  assert.ok(evil.includes('data-draft-text="&lt;script&gt;alert(1)&lt;/script&gt;"'));
});
