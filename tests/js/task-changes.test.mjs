// task-changes.test.mjs — fx/task.js 任务执行结果「本轮变化」区（工单
// task-changes-inline/01）：diff / 编译验证详情 / 错误行跳转 / 备份回滚 /
// 展开态；重复消除（无步骤报告 / checklist / feedback / 接线图）。
import test from "node:test";
import assert from "node:assert/strict";
import { taskChangesHTML } from "../../src/contest_generator/static/js/fx/task.js";

const verifiedData = {
  status: "verified",
  backup_id: "bak-1",
  compile: {
    exit_code: 0,
    summary: "编译通过",
    parsed_errors: [],
  },
  main_diff: {
    stats: { additions: 12, deletions: 3, hunks: 1 },
    hunks: [{ title: "循迹阈值", line: 88, lines: [
      { kind: "add", text: "    line_error = 0;", },
    ] }],
  },
};

test("taskChangesHTML: 渲染 details + 本轮变化 + 验证徽章", () => {
  const html = taskChangesHTML({ id: "t1" }, verifiedData, { open: true });
  assert.ok(html.startsWith('<details class="task-changes" open>'));
  assert.ok(html.includes("本轮变化"));
  assert.ok(html.includes("✓ 已通过编译验证"));
});

test("taskChangesHTML: open 缺省 = 不展开（details 无 open 属性）", () => {
  const html = taskChangesHTML({ id: "t1" }, verifiedData, {});
  assert.ok(html.startsWith('<details class="task-changes">'));
  assert.ok(!html.includes('<details class="task-changes" open>'));
});

test("taskChangesHTML: 数据缺失 = 空串（防御）", () => {
  assert.equal(taskChangesHTML({ id: "t1" }, null, {}), "");
  assert.equal(taskChangesHTML({ id: "t1" }, undefined, {}), "");
});

test("taskChangesHTML: diff 段 = 统计行 + hunk", () => {
  const html = taskChangesHTML({ id: "t1" }, verifiedData, { open: true });
  assert.ok(html.includes("新增 <span class=\"diff-count add\">+12</span> 行"));
  assert.ok(html.includes("循迹阈值"));
  assert.ok(html.includes("diff-hunk"));
});

test("taskChangesHTML: main_diff 为 null（空 hunks）= 占位提示，undefined = 无 diff 段", () => {
  const nullDiff = taskChangesHTML({ id: "t1" },
    { ...verifiedData, main_diff: null }, { open: true });
  assert.ok(nullDiff.includes("任务未改动 main.c（无差异）。"));
  const noDiff = taskChangesHTML({ id: "t1" },
    { ...verifiedData, main_diff: undefined }, { open: true });
  assert.ok(!noDiff.includes("diff-stats"));
  assert.ok(!noDiff.includes("无差异"));
});

test("taskChangesHTML: 错误行跳转段（有错才渲染）", () => {
  const data = { ...verifiedData, status: "failed", compile: {
    exit_code: 1,
    parsed_errors: [{ path: "main.c", line: 42, message: "expected ';'" }],
  } };
  const html = taskChangesHTML({ id: "t1" }, data, { open: true });
  assert.ok(html.includes('class="task-err-jump" data-line="42"'));
  assert.ok(html.includes("expected &#39;;&#39;"));  // esc 转义单引号
  // 无错误 → 无 .task-err-list
  assert.ok(!taskChangesHTML({ id: "t1" }, verifiedData, { open: true }).includes("task-err-list"));
});

test("taskChangesHTML: 备份行 + 回滚按钮（backup 空 = 无按钮）", () => {
  const html = taskChangesHTML({ id: "t1" }, verifiedData, { open: true });
  assert.ok(html.includes('已备份 · <button class="btn-task-rollback danger" data-backup="bak-1" data-task="t1"'));
  assert.ok(html.includes("回滚到本任务执行前"));
  assert.ok(!html.includes("备份：<span"));  // 原始备份 id 不上界面（工单 03）
  const noBackup = taskChangesHTML({ id: "t1" },
    { ...verifiedData, backup_id: "" }, { open: true });
  assert.ok(!noBackup.includes("已备份"));
  assert.ok(!noBackup.includes("btn-task-rollback"));
});

test("taskChangesHTML: unverified / failed 详情文案与结果面板一致", () => {
  const unv = taskChangesHTML({ id: "t1" },
    { ...verifiedData, status: "unverified" }, { open: true });
  assert.ok(unv.includes("未检测到编译工具链：任务结果已写入 main.c"));
  const failed = taskChangesHTML({ id: "t1" },
    { ...verifiedData, status: "failed" }, { open: true });
  assert.ok(failed.includes("编译验证未通过，任务结果已写入 main.c（已备份，可回滚）"));
});

test("taskChangesHTML: 重复消除——无步骤报告 / checklist / feedback / 接线图", () => {
  const html = taskChangesHTML({ id: "t1" }, verifiedData, { open: true });
  assert.ok(!html.includes("task-step-report"));
  assert.ok(!html.includes("上板自检清单"));
  assert.ok(!html.includes("task-check"));
  assert.ok(!html.includes("上板反馈"));
  assert.ok(!html.includes("data-wiring-uid"));
  assert.ok(!html.includes("下一步要做"));
});

test("taskChangesHTML: 含 HTML 字符的 id / 备份 / 错误内容被转义", () => {
  const data = { ...verifiedData, backup_id: 'a&"b', compile: {
    exit_code: 2, parsed_errors: [{ path: "main.c", line: 1, message: "<script>" }],
  } };
  const html = taskChangesHTML({ id: 't<&"1' }, data, { open: true });
  assert.ok(html.includes("a&amp;&quot;b"));
  assert.ok(html.includes("t&lt;&amp;&quot;1"));
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes('data-task="t<"'));
});
