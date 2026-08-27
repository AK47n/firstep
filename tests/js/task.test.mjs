// task.test.mjs — fx/task.js 任务推进纯函数（工单 task-progress/01）：
// 状态徽章文案 / 验收方式标注 / 评分点引用 / 任务卡渲染 / 进度汇总 / 错误文案。
import test from "node:test";
import assert from "node:assert/strict";
import {
  taskStatusLabel, taskStatusBadgeClass, taskVerifyLabel,
  taskScoreRefsText, taskCardHTML, tasksGridHTML, tasksProgressText,
  taskCardActions, verifyStatusMarkup,
  taskCanFeedback, taskIterationLabel, taskIterationsHTML, taskLatestFeedbackNote,
  taskOrderLabel, taskDialogAdoptHTML, taskDialogButtonHTML, taskDialogAreaHTML,
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

test("taskDialogButtonHTML: doing 不显示；open 切换文案", () => {
  assert.equal(taskDialogButtonHTML({ id: "t1", status: "doing" }, null), "");
  const closed = taskDialogButtonHTML({ id: "t1", status: "pending" }, { open: false });
  assert.ok(closed.includes("和 AI 商量"));
  assert.ok(closed.includes("data-task=\"t1\""));
  const open = taskDialogButtonHTML({ id: "t1", status: "verified" }, { open: true });
  assert.ok(open.includes("收起讨论"));
});

test("taskDialogAreaHTML: 未展开 → 空串；展开空历史 → 引导语；有历史 → 消息 + 采纳按钮", () => {
  assert.equal(taskDialogAreaHTML({ id: "t1" }, { open: false }), "");
  const empty = taskDialogAreaHTML({ id: "t1" }, { open: true, history: [], busy: false });
  assert.ok(empty.includes("可以告诉 AI 你的想法或纠正"));
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
