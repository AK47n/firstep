// wait 纯函数单测（工单 ux-walkthrough-02/12）：长任务秒表文案——
// waitLabel 复用 fmtClock（0 秒 / 1 分 / 小时级进位），WAIT_GENERIC_LINE
// 无阶段通用行。
import test from "node:test";
import assert from "node:assert/strict";
import {
  waitLabel, WAIT_GENERIC_LINE,
} from "../../src/contest_generator/static/js/fx/wait.js";

test("waitLabel：0 秒 / 1 分 / 小时级进位（mm:ss 两位补零，分可超 59——与 fmtClock 同源）", () => {
  assert.equal(waitLabel(0), "已等待 00:00");
  assert.equal(waitLabel(1), "已等待 00:01");
  assert.equal(waitLabel(59), "已等待 00:59");
  assert.equal(waitLabel(60), "已等待 01:00");
  assert.equal(waitLabel(65), "已等待 01:05");
  assert.equal(waitLabel(3700), "已等待 61:40");   // 小时级：分超 59 不折叠成时
});

test("WAIT_GENERIC_LINE：无阶段场景通用行（含分钟级提示）", () => {
  assert.match(WAIT_GENERIC_LINE, /AI 正在处理/);
  assert.match(WAIT_GENERIC_LINE, /几分钟/);
});
