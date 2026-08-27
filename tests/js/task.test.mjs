// task.test.mjs — fx/task.js 任务推进纯函数（工单 task-progress/01）：
// 状态徽章文案 / 验收方式标注 / 评分点引用 / 任务卡渲染 / 进度汇总 / 错误文案。
import test from "node:test";
import assert from "node:assert/strict";
import {
  taskStatusLabel, taskStatusBadgeClass, taskVerifyLabel,
  taskScoreRefsText, taskCardHTML, tasksGridHTML, tasksProgressText,
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
