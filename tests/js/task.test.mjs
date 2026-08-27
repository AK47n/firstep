// task.test.mjs — fx/task.js 任务推进纯函数（工单 task-progress/01）：
// 状态徽章文案 / 验收方式标注 / 评分点引用 / 任务卡渲染 / 进度汇总 / 错误文案。
import test from "node:test";
import assert from "node:assert/strict";
import {
  taskStatusLabel, taskStatusBadgeClass, taskVerifyLabel,
  taskScoreRefsText, taskCardHTML, tasksGridHTML, tasksProgressText,
  taskCardActions, verifyStatusMarkup,
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
