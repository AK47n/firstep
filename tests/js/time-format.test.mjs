// 进度面板时间格式化纯函数单测（前端 ES 模块化阶段 2 工单 03）：
// fmtClock / fmtDuration 已迁 static/js/fx/core.js，直接 import 直测。
// 运行：node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";
import { fmtClock, fmtDuration } from "../../src/contest_generator/static/js/fx/core.js";

test("fmtClock：mm:ss（分可超 59，秒向下取整）", () => {
  assert.equal(fmtClock(0), "00:00");
  assert.equal(fmtClock(59.9), "00:59");
  assert.equal(fmtClock(61), "01:01");
  assert.equal(fmtClock(3661), "61:01");
});

test("fmtDuration：小时/分/秒段（完成行文案）", () => {
  assert.equal(fmtDuration(45), "45 秒");
  assert.equal(fmtDuration(754), "12 分 34 秒");
  assert.equal(fmtDuration(3723), "1 小时 2 分 3 秒");
  assert.equal(fmtDuration(60), "1 分 0 秒");
});
